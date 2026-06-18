"""
XRPL Client wrapper for Testnet operations

Handles:
- Payment submission
- Balance queries
- Transaction verification
- Account validation
"""

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.transaction import submit_and_wait
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.account import get_balance
from xrpl.core.addresscodec import is_valid_classic_address
from decimal import Decimal
from datetime import datetime

# XRPL Testnet endpoint
TESTNET_URL = "https://s.altnet.rippletest.net:51234"


def validate_xrpl_address(address: str) -> bool:
    """Validate an XRPL address using cryptographic checksum verification."""
    if not address:
        return False
    try:
        return is_valid_classic_address(address)
    except Exception:
        return False


class XRPLClient:
    """XRPL Testnet client wrapper"""
    
    def __init__(self):
        self.client = JsonRpcClient(TESTNET_URL)
    
    def validate_address(self, address: str) -> bool:
        """Cryptographically validate an XRPL classic address (base58 + checksum)."""
        try:
            from xrpl.core.addresscodec import is_valid_classic_address
            return is_valid_classic_address(address)
        except Exception:
            return False
    
    def get_wallet_from_seed(self, seed: str) -> Wallet:
        """
        Create a Wallet object from a seed.
        
        Args:
            seed: XRPL seed string
            
        Returns:
            Wallet object
            
        Raises:
            Exception if seed is invalid
        """
        try:
            return Wallet.from_seed(seed)
        except Exception as e:
            raise ValueError(f"Invalid XRPL seed: {str(e)}")
    
    def get_balance(self, address: str) -> dict:
        """
        Get XRP balance for an address.
        
        Args:
            address: XRPL address
            
        Returns:
            Dict with balance info: {'xrp': float, 'drops': str}
        """
        try:
            balance_drops = get_balance(address, self.client)
            balance_xrp = drops_to_xrp(balance_drops)
            return {
                'xrp': float(balance_xrp),
                'drops': balance_drops
            }
        except Exception as e:
            raise Exception(f"Failed to get balance: {str(e)}")
    
    def send_xrp_payment(
        self, 
        sender_seed: str, 
        destination: str, 
        amount_xrp: float,
        memo: str = None
    ) -> dict:
        """
        Send XRP payment on Testnet.
        
        Args:
            sender_seed: Sender's XRPL seed
            destination: Recipient's XRPL address
            amount_xrp: Amount in XRP
            memo: Optional memo text
            
        Returns:
            Dict with transaction details: {
                'hash': str,
                'result': str,
                'validated': bool
            }
        """
        try:
            # Create wallet from seed
            wallet = self.get_wallet_from_seed(sender_seed)
            
            # Convert XRP to drops
            amount_drops = xrp_to_drops(Decimal(str(amount_xrp)))
            
            # Prepare memos if provided
            memos = None
            if memo:
                from xrpl.models.transactions import Memo
                memos = [
                    Memo(
                        memo_data=memo.encode().hex()
                    )
                ]
            
            # Create payment transaction
            payment_tx = Payment(
                account=wallet.address,
                destination=destination,
                amount=amount_drops,
                memos=memos
            )

            
            # Submit and wait for validation
            response = submit_and_wait(payment_tx, self.client, wallet)
            
            return {
                'hash': response.result.get('hash'),
                'result': response.result.get('meta', {}).get('TransactionResult'),
                'validated': response.is_successful(),
                'ledger_index': response.result.get('ledger_index')
            }
            
        except Exception as e:
            raise Exception(f"Payment failed: {str(e)}")
    
    def verify_transaction(self, tx_hash: str) -> dict:
        """
        Verify a transaction by hash.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Dict with transaction info
        """
        try:
            from xrpl.models.requests import Tx
            request = Tx(transaction=tx_hash)
            response = self.client.request(request)
            
            if response.is_successful():
                return {
                    'validated': response.result.get('validated', False),
                    'result': response.result.get('meta', {}).get('TransactionResult'),
                    'ledger_index': response.result.get('ledger_index'),
                    'date': response.result.get('date')
                }
            else:
                raise Exception("Transaction not found")
                
        except Exception as e:
            raise Exception(f"Verification failed: {str(e)}")
    
    def create_escrow(
        self,
        sender_seed: str,
        destination: str,
        amount_xrp: float,
        condition_hex: str,
        cancel_after_dt: datetime,
        memo: str = None
    ) -> dict:
        """Create a conditional XRPL escrow (XRP only).
        Funds are locked until EscrowFinish (with fulfillment) or EscrowCancel (after cancel_after).
        Only classic XRPL EscrowCreate is supported — token escrow (XLS-85) is out of scope.

        Returns {'hash', 'offer_sequence', 'validated', 'result'}
        offer_sequence is required for EscrowFinish/EscrowCancel.
        """
        try:
            from xrpl.models.transactions import EscrowCreate, Memo
            from xrpl.utils import datetime_to_ripple_time

            wallet = self.get_wallet_from_seed(sender_seed)
            amount_drops = xrp_to_drops(Decimal(str(amount_xrp)))
            cancel_after_ripple = datetime_to_ripple_time(cancel_after_dt)

            memos = None
            if memo:
                memos = [Memo(memo_data=memo.encode().hex())]

            tx = EscrowCreate(
                account=wallet.address,
                destination=destination,
                amount=amount_drops,
                condition=condition_hex,
                cancel_after=cancel_after_ripple,
                memos=memos,
            )

            response = submit_and_wait(tx, self.client, wallet)

            # offer_sequence is the Sequence of the EscrowCreate tx itself
            offer_sequence = response.result.get("Sequence") or response.result.get("tx_json", {}).get("Sequence")

            return {
                "hash": response.result.get("hash"),
                "offer_sequence": offer_sequence,
                "validated": response.is_successful(),
                "result": response.result.get("meta", {}).get("TransactionResult"),
            }
        except Exception as e:
            raise Exception(f"EscrowCreate failed: {str(e)}")

    def finish_escrow(
        self,
        sender_seed: str,
        owner_address: str,
        offer_sequence: int,
        condition_hex: str,
        fulfillment_hex: str,
    ) -> dict:
        """Release a conditional escrow by providing the fulfillment preimage.
        Can be called by anyone — funds always go to the original escrow destination.
        Fee is auto-calculated (scales with fulfillment size).

        Returns {'hash', 'validated', 'result'}
        """
        try:
            from xrpl.models.transactions import EscrowFinish

            wallet = self.get_wallet_from_seed(sender_seed)

            tx = EscrowFinish(
                account=wallet.address,
                owner=owner_address,
                offer_sequence=offer_sequence,
                condition=condition_hex,
                fulfillment=fulfillment_hex,
            )

            response = submit_and_wait(tx, self.client, wallet)

            return {
                "hash": response.result.get("hash"),
                "validated": response.is_successful(),
                "result": response.result.get("meta", {}).get("TransactionResult"),
            }
        except Exception as e:
            raise Exception(f"EscrowFinish failed: {str(e)}")

    def cancel_escrow(
        self,
        sender_seed: str,
        owner_address: str,
        offer_sequence: int,
    ) -> dict:
        """Cancel an expired escrow and return funds to the creator.
        IMPORTANT: EscrowCancel is only valid AFTER the CancelAfter time has passed.
        Calling before expiry will fail with tecNO_PERMISSION.

        Returns {'hash', 'validated', 'result'}
        """
        try:
            from xrpl.models.transactions import EscrowCancel

            wallet = self.get_wallet_from_seed(sender_seed)

            tx = EscrowCancel(
                account=wallet.address,
                owner=owner_address,
                offer_sequence=offer_sequence,
            )

            response = submit_and_wait(tx, self.client, wallet)

            return {
                "hash": response.result.get("hash"),
                "validated": response.is_successful(),
                "result": response.result.get("meta", {}).get("TransactionResult"),
            }
        except Exception as e:
            raise Exception(f"EscrowCancel failed: {str(e)}")

    def get_testnet_explorer_url(self, tx_hash: str) -> str:
        """
        Get the Testnet explorer URL for a transaction.
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Explorer URL string
        """
        return f"https://testnet.xrpl.org/transactions/{tx_hash}"


# Simulated token conversions (for MVP)
# In production, these would use actual DEX rates or oracles
MOCK_EXCHANGE_RATES = {
    'XRP_MXN': 20.0,      # 1 XRP = 20 MXN (example)
    'USDC_MXN': 17.5,     # 1 USDC = 17.5 MXN
    'RLUSD_MXN': 17.5,    # 1 RLUSD = 17.5 MXN
    'MXN_MXN': 1.0        # 1 MXN = 1 MXN
}


def convert_mxn_to_token(amount_mxn: float, token: str) -> float:
    """
    Convert MXN amount to token amount using mock rates.
    
    Args:
        amount_mxn: Amount in Mexican Pesos
        token: Token symbol (XRP, USDC, RLUSD, MXN)
        
    Returns:
        Amount in the specified token
    """
    rate_key = f"{token}_MXN"
    if rate_key not in MOCK_EXCHANGE_RATES:
        raise ValueError(f"Unsupported token: {token}")
    
    rate = MOCK_EXCHANGE_RATES[rate_key]
    return amount_mxn / rate


def convert_token_to_mxn(amount_token: float, token: str) -> float:
    """
    Convert token amount to MXN using mock rates.
    
    Args:
        amount_token: Amount in token
        token: Token symbol (XRP, USDC, RLUSD, MXN)
        
    Returns:
        Amount in Mexican Pesos
    """
    rate_key = f"{token}_MXN"
    if rate_key not in MOCK_EXCHANGE_RATES:
        raise ValueError(f"Unsupported token: {token}")
    
    rate = MOCK_EXCHANGE_RATES[rate_key]
    return amount_token * rate
