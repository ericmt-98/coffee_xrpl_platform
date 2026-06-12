"""
PDF receipt generator using QTextDocument + QPrinter (no extra dependencies).
"""


def generate_receipt_pdf(payment_data: dict, file_path: str) -> None:
    """
    Render an HTML receipt to a PDF file.

    payment_data keys:
        uetr, tx_hash, producer_name, operator_name,
        weight_kg, price_per_kg, total_mxn, token_amount,
        currency, timestamp
    """
    from PySide6.QtGui import QTextDocument
    from PySide6.QtPrintSupport import QPrinter

    uetr         = payment_data.get('uetr', '—')
    tx_hash      = payment_data.get('tx_hash', '—')
    producer     = payment_data.get('producer_name', '—')
    operator     = payment_data.get('operator_name', '—')
    weight       = float(payment_data.get('weight_kg', 0))
    price        = float(payment_data.get('price_per_kg', 0))
    total_mxn    = float(payment_data.get('total_mxn', 0))
    token_amount = float(payment_data.get('token_amount', 0))
    currency     = payment_data.get('currency', '—')
    timestamp    = payment_data.get('timestamp', '—')

    html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body      {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; color: #201F1E; }}
  h1        {{ color: #0078D4; font-size: 20pt; margin-bottom: 4px; }}
  h2        {{ font-size: 11pt; color: #605E5C; border-bottom: 1px solid #E1E1E1;
               padding-bottom: 4px; margin-top: 20px; }}
  table     {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
  td        {{ padding: 5px 4px; font-size: 10pt; }}
  td.label  {{ font-weight: 600; color: #605E5C; width: 40%; }}
  .amount   {{ font-size: 16pt; font-weight: bold; color: #107C10; }}
  .mono     {{ font-family: 'Courier New'; font-size: 8pt; word-break: break-all; }}
  .footer   {{ font-size: 8pt; color: #A19F9D; margin-top: 30px; text-align: center; }}
</style>
</head>
<body>
<h1>&#9749; Coffee XRPL Platform &mdash; Recibo de Pago</h1>
<p style="font-size:9pt; color:#605E5C; margin-top:2px;">Fecha: {timestamp}</p>

<h2>Identificadores</h2>
<table>
  <tr><td class="label">UETR</td><td class="mono">{uetr}</td></tr>
  <tr><td class="label">Hash XRPL</td><td class="mono">{tx_hash}</td></tr>
</table>

<h2>Partes</h2>
<table>
  <tr><td class="label">Operador</td><td>{operator}</td></tr>
  <tr><td class="label">Productor</td><td>{producer}</td></tr>
</table>

<h2>Entrega de Caf&eacute;</h2>
<table>
  <tr><td class="label">Peso</td><td>{weight:.2f} kg</td></tr>
  <tr><td class="label">Precio por kg</td><td>${price:.2f} MXN</td></tr>
  <tr><td class="label">Total MXN</td><td class="amount">${total_mxn:.2f} MXN</td></tr>
  <tr><td class="label">Token enviado</td><td>{token_amount:.6f} {currency}</td></tr>
</table>

<p class="footer">
  Plataforma educativa &mdash; XRPL Testnet.<br>
  Esta transacci&oacute;n no tiene valor monetario real.<br>
  Generado por Coffee XRPL Platform
</p>
</body>
</html>"""

    doc = QTextDocument()
    doc.setHtml(html)

    printer = QPrinter()
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(file_path)
    doc.print_(printer)
