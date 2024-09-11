import json

def generate_html_report(data, output_filename):
    """Generates an HTML report from the signature validation data.

    Args:
        data (dict): The signature validation data.
        output_filename (str): The name of the output HTML file.
    """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Document Signature Validation Report</title>
        <style>
            body {{
                font-family: sans-serif;
            }}
            h1, h2, h3 {{
                margin-top: 1.5em;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 1em;
            }}
            th, td {{
                border: 1px solid black;
                padding: 8px;
                text-align: left;
                vertical-align: top;  /* Align text to the top of the cell */
            }}
            th {{
                background-color: lightgray;
            }}
        </style>
    </head>
    <body>
        <h1>Document Signature Validation Report</h1>

        <h2>Document Information</h2>
        <table>
            <tr>
                <th>Document Name</th>
                <td>{data['DiagnosticData']['DocumentName']}</td>
            </tr>
            <tr>
                <th>Validation Date</th>
                <td>{data['DiagnosticData']['ValidationDate']}</td>
            </tr>
        </table>
    """

    # --- Signatures ---
    for signature_data in data['SimpleReport']['signatureOrTimestampOrEvidenceRecord']:
        signature = signature_data['Signature']
        html_content += f"""
        <h2>Signature</h2>

        <h3>Signer Information</h3>
        <table>
            <tr>
                <th>Signer Name</th>
                <td>{signature['SignedBy']}</td>
            </tr>
            <tr>
                <th>Signing Time</th>
                <td>{signature['SigningTime']}</td>
            </tr>
            <tr>
                <th>Signature Format</th>
                <td>{signature['SignatureFormat']}</td>
            </tr>
            <tr>
                <th>Signature Status</th>
                <td>{signature['Indication']}</td>
            </tr>
        </table>

        <h3>Certificate Chain</h3>
        <table>
            <tr>
                <th>Certificate Subject</th>
            </tr>
        """

        for cert in signature['CertificateChain']['Certificate']:
            name_parts = cert['QualifiedName'].split(',')
            formatted_name = '<br>'.join(name_parts)
            html_content += f"""
            <tr>
                <td>{formatted_name}</td>
            </tr>
            """

        # --- Modification Detection (using data from DiagnosticData) ---
        for sig in data['DiagnosticData']['Signature']:
            if sig['Id'] == signature['Id']:
                modified_pages = [str(diff['Page']) for diff in sig["PDFRevision"]["ModificationDetection"]["VisualDifference"]]
                break

        html_content += """
        </table>

        <h3>Modification Detection</h3>
        """

        if modified_pages:
            modification_text = f"Visual differences detected on pages: {', '.join(modified_pages)}"
        else:
            modification_text = "No visual differences detected."
        html_content += f"<p>{modification_text}</p>"

    # --- Document Validity ---
    doc_validity = data['DetailedReport']['signatureOrTimestampOrEvidenceRecord'][0]['Signature']['ValidationProcessBasicSignature']['Conclusion']
    html_content += f"""
    <h2>Document Validity</h2>
    <table>
            <tr>
                <th>Document Status</th>
                <td>{doc_validity['Indication']}</td>
            </tr>
            <tr>
                <th>Document Subindication</th>
                <td>{doc_validity['SubIndication']}</td>
            </tr>
    </table>
    </body>
    </html>
    """

    with open(output_filename, "w", encoding="utf-8") as html_file:
        html_file.write(html_content)

# Load JSON and generate HTML report 
with open("validation_response.json", "r", encoding="utf-8") as json_file:
    validation_data = json.load(json_file)

generate_html_report(validation_data, "signature_report.html")