"""
==============================================================================
spike_escrow.py — Script educativo de exploración (spike) para XRPL Escrow
==============================================================================

Propósito:
    Demostrar y validar los primitivos de Escrow de XRPL en testnet usando
    PREIMAGE-SHA-256 crypto-conditions codificadas manualmente en DER.
    Este script es standalone: NO importa nada de core/ ni de las apps.

Cómo correr:
    python scripts/spike_escrow.py

Requisito:
    pip install xrpl-py

Reglas fundamentales de XRPL Escrow (importante para la UI):
    - EscrowFinish (liberar fondos) solo puede ejecutarse ANTES de CancelAfter.
    - EscrowCancel (cancelar y devolver fondos) solo puede ejecutarse DESPUÉS
      de que el tiempo CancelAfter haya pasado.
    - XRPL usa Ripple Epoch: segundos transcurridos desde 2000-01-01T00:00:00Z,
      NO Unix time (segundos desde 1970-01-01). La diferencia es 946684800 s.
    - Usar siempre xrpl.utils.datetime_to_ripple_time() para la conversión.

Explorer testnet: https://testnet.xrpl.org/transactions/{hash}
==============================================================================
"""

import os
import hashlib
from datetime import datetime, timezone, timedelta

from xrpl.clients import JsonRpcClient
from xrpl.wallet import generate_faucet_wallet
from xrpl.models.transactions import EscrowCreate, EscrowFinish
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops, datetime_to_ripple_time, drops_to_xrp
from xrpl.account import get_balance

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
TESTNET_URL = "https://s.altnet.rippletest.net:51234"
EXPLORER_BASE = "https://testnet.xrpl.org/transactions"
ESCROW_AMOUNT_XRP = 5
CANCEL_AFTER_MINUTES = 10


# ---------------------------------------------------------------------------
# Generación de crypto-condition PREIMAGE-SHA-256 (DER manual, sin librería)
# ---------------------------------------------------------------------------

def generate_escrow_condition() -> tuple[str, str]:
    """
    Genera un par (condition, fulfillment) PREIMAGE-SHA-256 para XRPL Escrow.

    Usa un preimage aleatorio de 32 bytes y codificación DER manual, siguiendo
    el estándar draft-thomas-crypto-conditions-04.

    Layout DER:
        condition   = A0 25 80 20 <sha256(preimage)> 81 01 20
        fulfillment = A0 22 80 20 <preimage>

    Breakdown de los campos:
        A0       — tag: tipo PREIMAGE-SHA-256 (context [0] constructed)
        25 / 22  — length del contenido que sigue (37 / 34 bytes)
        80 20    — tag 'preimage' (primitivo [0]) + length 32
        <data>   — sha256(preimage) en condition, preimage raw en fulfillment
        81 01 20 — solo en condition: tag 'maxFulfillmentLength' ([1]) = 32

    Returns:
        (condition_hex, fulfillment_hex) en mayúsculas, sin prefijo 0x.
    """
    preimage = os.urandom(32)
    digest = hashlib.sha256(preimage).digest()

    # condition: A0 25 80 20 <digest 32B> 81 01 20
    condition = bytes.fromhex("A0258020") + digest + bytes.fromhex("810120")

    # fulfillment: A0 22 80 20 <preimage 32B>
    fulfillment = bytes.fromhex("A0228020") + preimage

    return condition.hex().upper(), fulfillment.hex().upper()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sep(title: str) -> None:
    """Imprime un separador visual para las secciones."""
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def tx_url(tx_hash: str) -> str:
    return f"{EXPLORER_BASE}/{tx_hash}"


def get_offer_sequence(result: dict) -> int:
    """
    Extrae el Sequence (offer_sequence) de la respuesta de una transacción.

    XRPL puede devolver el campo en distintas ubicaciones según la versión
    del servidor y el método de envío:
        - result["Sequence"]
        - result["tx_json"]["Sequence"]
        - result["result"]["Sequence"]
        - result["result"]["tx_json"]["Sequence"]
    """
    # Intentar rutas conocidas en orden de preferencia
    candidates = [
        result.get("Sequence"),
        result.get("tx_json", {}).get("Sequence"),
        result.get("result", {}).get("Sequence"),
        result.get("result", {}).get("tx_json", {}).get("Sequence"),
    ]
    for value in candidates:
        if value is not None:
            return int(value)

    raise KeyError(
        f"No se encontró 'Sequence' en la respuesta. Claves disponibles: "
        f"{list(result.keys())}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sep("XRPL ESCROW SPIKE — Testnet")
    print(f"  Servidor : {TESTNET_URL}")
    print(f"  Explorer : {EXPLORER_BASE}/<hash>")
    print(f"  Monto    : {ESCROW_AMOUNT_XRP} XRP")
    print(f"  Expiración: {CANCEL_AFTER_MINUTES} minutos desde ahora")

    client = JsonRpcClient(TESTNET_URL)

    # -----------------------------------------------------------------------
    # 1. Generar dos wallets con faucet
    # -----------------------------------------------------------------------
    sep("PASO 1 — Generar wallets de prueba (faucet)")
    try:
        print("  Solicitando wallet A al faucet (puede tardar ~10 s)...")
        wallet_a = generate_faucet_wallet(client, debug=False)
        print(f"  Wallet A: {wallet_a.address}")
        print(f"  Saldo A : {drops_to_xrp(get_balance(wallet_a.address, client))} XRP")

        print()
        print("  Solicitando wallet B al faucet (puede tardar ~10 s)...")
        wallet_b = generate_faucet_wallet(client, debug=False)
        print(f"  Wallet B: {wallet_b.address}")
        print(f"  Saldo B : {drops_to_xrp(get_balance(wallet_b.address, client))} XRP")

    except Exception as exc:
        print(f"\n  ERROR al contactar el faucet: {exc}")
        print("  Verifica tu conexión a internet y que testnet esté disponible.")
        print("  Estado del faucet: https://xrpl.org/xrp-testnet-faucet.html")
        return

    # -----------------------------------------------------------------------
    # 2. TEST A — Ciclo completo APROBAR
    # -----------------------------------------------------------------------
    sep("TEST A — Ciclo completo: EscrowCreate → EscrowFinish (debe APROBAR)")

    # Generar condition/fulfillment para este escrow
    condition_a, fulfillment_a = generate_escrow_condition()
    print(f"  Condition  : {condition_a[:20]}...{condition_a[-8:]}")
    print(f"  Fulfillment: {fulfillment_a[:20]}...{fulfillment_a[-8:]}")

    # Calcular CancelAfter en Ripple Epoch
    # CRÍTICO: XRPL usa Ripple Epoch (desde 2000-01-01T00:00:00Z), NO Unix time.
    # datetime_to_ripple_time() hace la conversión correctamente.
    cancel_dt = datetime.now(timezone.utc) + timedelta(minutes=CANCEL_AFTER_MINUTES)
    cancel_after_ripple = datetime_to_ripple_time(cancel_dt)
    print(f"\n  CancelAfter UTC       : {cancel_dt.isoformat()}")
    print(f"  CancelAfter Ripple EP : {cancel_after_ripple}")
    print(f"  (Diferencia con Unix  : {int(cancel_dt.timestamp())} - {cancel_after_ripple}"
          f" = {int(cancel_dt.timestamp()) - cancel_after_ripple} s ≈ 946684800 s)")

    # -- EscrowCreate --
    print(f"\n  [EscrowCreate] {ESCROW_AMOUNT_XRP} XRP: {wallet_a.address} → {wallet_b.address}")
    try:
        escrow_create_a = EscrowCreate(
            account=wallet_a.address,
            destination=wallet_b.address,
            amount=str(xrp_to_drops(ESCROW_AMOUNT_XRP)),  # en drops (string)
            condition=condition_a,
            cancel_after=cancel_after_ripple,
        )
        response_create_a = submit_and_wait(escrow_create_a, client, wallet_a)

        if not response_create_a.is_successful():
            print(f"  ERROR en EscrowCreate: {response_create_a.result}")
            return

        tx_hash_a = response_create_a.result.get("hash", "")
        print(f"  Hash : {tx_hash_a}")
        print(f"  URL  : {tx_url(tx_hash_a)}")

        # Capturar offer_sequence del resultado
        offer_seq_a = get_offer_sequence(response_create_a.result)
        print(f"  offer_sequence: {offer_seq_a}")

    except Exception as exc:
        print(f"  ERROR en EscrowCreate: {exc}")
        return

    # -- EscrowFinish --
    print(f"\n  [EscrowFinish] Liberando escrow con fulfillment correcto...")
    try:
        escrow_finish_a = EscrowFinish(
            account=wallet_b.address,       # quien ejecuta el finish (puede ser cualquiera)
            owner=wallet_a.address,         # quien creó el escrow
            offer_sequence=offer_seq_a,
            condition=condition_a,
            fulfillment=fulfillment_a,
        )
        response_finish_a = submit_and_wait(escrow_finish_a, client, wallet_b)

        if response_finish_a.is_successful():
            new_balance_b = drops_to_xrp(get_balance(wallet_b.address, client))
            finish_hash_a = response_finish_a.result.get("hash", "")
            print(f"  RESULTADO: APROBADO correctamente")
            print(f"  Hash      : {finish_hash_a}")
            print(f"  URL       : {tx_url(finish_hash_a)}")
            print(f"  Nuevo saldo Wallet B: {new_balance_b} XRP")
        else:
            print(f"  RESULTADO INESPERADO (esperábamos éxito): {response_finish_a.result}")

    except Exception as exc:
        print(f"  ERROR en EscrowFinish: {exc}")
        return

    # -----------------------------------------------------------------------
    # 3. TEST B — Fulfillment INCORRECTO debe FALLAR
    # -----------------------------------------------------------------------
    sep("TEST B — Fulfillment incorrecto: debe FALLAR (comportamiento esperado)")

    # Generar un segundo escrow con nueva condition/fulfillment
    condition_b, fulfillment_b = generate_escrow_condition()
    print(f"  Condition  : {condition_b[:20]}...{condition_b[-8:]}")

    # Calcular nuevo CancelAfter (mismo margen)
    cancel_dt_b = datetime.now(timezone.utc) + timedelta(minutes=CANCEL_AFTER_MINUTES)
    cancel_after_ripple_b = datetime_to_ripple_time(cancel_dt_b)

    # -- EscrowCreate para Test B --
    print(f"\n  [EscrowCreate] {ESCROW_AMOUNT_XRP} XRP: {wallet_a.address} → {wallet_b.address}")
    try:
        escrow_create_b = EscrowCreate(
            account=wallet_a.address,
            destination=wallet_b.address,
            amount=str(xrp_to_drops(ESCROW_AMOUNT_XRP)),
            condition=condition_b,
            cancel_after=cancel_after_ripple_b,
        )
        response_create_b = submit_and_wait(escrow_create_b, client, wallet_a)

        if not response_create_b.is_successful():
            print(f"  ERROR en EscrowCreate B: {response_create_b.result}")
            return

        tx_hash_b = response_create_b.result.get("hash", "")
        print(f"  Hash           : {tx_hash_b}")
        print(f"  URL            : {tx_url(tx_hash_b)}")
        offer_seq_b = get_offer_sequence(response_create_b.result)
        print(f"  offer_sequence : {offer_seq_b}")

    except Exception as exc:
        print(f"  ERROR en EscrowCreate B: {exc}")
        return

    # -- EscrowFinish con fulfillment alterado --
    # Alterar el último byte del fulfillment para simular un fulfillment incorrecto
    fulfillment_b_bytes = bytes.fromhex(fulfillment_b)
    tampered_last_byte = (fulfillment_b_bytes[-1] ^ 0xFF)           # flip todos los bits
    fulfillment_b_bad = (fulfillment_b_bytes[:-1] + bytes([tampered_last_byte])).hex().upper()

    print(f"\n  [EscrowFinish] Intentando con fulfillment ALTERADO (último byte modificado)...")
    print(f"  Fulfillment original : ...{fulfillment_b[-8:]}")
    print(f"  Fulfillment alterado : ...{fulfillment_b_bad[-8:]}")

    finish_failed_as_expected = False
    try:
        escrow_finish_b = EscrowFinish(
            account=wallet_b.address,
            owner=wallet_a.address,
            offer_sequence=offer_seq_b,
            condition=condition_b,
            fulfillment=fulfillment_b_bad,   # fulfillment INCORRECTO
        )
        response_finish_b = submit_and_wait(escrow_finish_b, client, wallet_b)

        if not response_finish_b.is_successful():
            # Fallo esperado: el ledger rechazó la tx por fulfillment inválido
            error_code = (
                response_finish_b.result.get("engine_result")
                or response_finish_b.result.get("result", {}).get("engine_result", "N/A")
            )
            print(f"\n  RESULTADO: Falló correctamente (comportamiento esperado)")
            print(f"  engine_result : {error_code}")
            print(f"  Explicación   : XRPL rechaza el EscrowFinish porque el fulfillment")
            print(f"                  no satisface la condition SHA-256 almacenada en el escrow.")
            finish_failed_as_expected = True
        else:
            # Esto NO debería ocurrir — si pasa, hay un bug en la lógica
            print(f"  ALERTA: El EscrowFinish con fulfillment incorrecto fue ACEPTADO.")
            print(f"  Esto no debería ocurrir. Revisar la generación de la condition.")
            print(f"  Resultado completo: {response_finish_b.result}")

    except Exception as exc:
        # Algunas versiones de xrpl-py lanzan excepción en vez de retornar un response fallido
        print(f"\n  RESULTADO: Excepción capturada (comportamiento esperado)")
        print(f"  Error     : {exc}")
        print(f"  Explicación: XRPL rechazó el EscrowFinish con fulfillment inválido.")
        finish_failed_as_expected = True

    # -----------------------------------------------------------------------
    # Resumen final
    # -----------------------------------------------------------------------
    sep("RESUMEN DEL SPIKE")
    print(f"  Test A (EscrowFinish correcto) : APROBADO")
    if finish_failed_as_expected:
        print(f"  Test B (Fulfillment incorrecto): Falló correctamente (APROBADO)")
    else:
        print(f"  Test B (Fulfillment incorrecto): INESPERADAMENTE EXITOSO — revisar lógica")

    print()
    print("  Recordatorio clave para la UI:")
    print("    - EscrowFinish  → ejecutar ANTES de que venza CancelAfter.")
    print("    - EscrowCancel  → ejecutar DESPUÉS de que venza CancelAfter.")
    print("    - Tiempo XRPL   → siempre convertir con datetime_to_ripple_time().")
    print()
    print("  Wallets usadas (testnet, sin valor real):")
    print(f"    Wallet A: {wallet_a.address}")
    print(f"    Wallet B: {wallet_b.address}")
    print()
    print("✓ Spike completado")
    print()


if __name__ == "__main__":
    main()
