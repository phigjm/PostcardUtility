#!/usr/bin/env python3
"""
Standalone Python script to generate a PDF invoice in DIN A4 format.
Uses ReportLab library for PDF generation.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os


class HLine(Flowable):
    """Horizontal line flowable"""
    def __init__(self, width='100%', thickness=1, color=colors.black):
        Flowable.__init__(self)
        self.width = width
        self.thickness = thickness
        self.color = color

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.height/2, self.width, self.height/2)

def create_invoice_pdf(
    output_path,
    sender_address,
    customer_address,
    delivery_address,
    invoice_date,
    invoice_number,
    postcard_id,
    printing_costs,
    shipping_cost,
    voucher,
    is_international_shipping,
    customer_name=None,
    customer_email=None,
    customer_username=None,
    vat_amount=0.0,
    total_amount=0.0
):
    """
    Create a PDF invoice.

    Args:
        output_path: Path where to save the PDF
        sender_address: String with sender address
        customer_address: String with customer billing address
        delivery_address: String with delivery address
        invoice_date: Date string (e.g., '2024-01-04')
        invoice_number: String with invoice number
        postcard_id: String with postcard ID
        printing_costs: Printing costs amount
        shipping_cost: Shipping costs amount
        voucher: Voucher amount (negative for discount)
        is_international_shipping: Boolean for international shipping description
        customer_name: Optional customer name
        customer_email: Optional customer email
        customer_username: Optional customer username
        vat_amount: VAT amount in EUR
        total_amount: Total amount in EUR
    """

    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2.5*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # Get styles
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1  # Center
    )

    address_style = styles['Normal']
    address_style.fontSize = 10

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=10,
        alignment=2  # Right
    )

    # Function to draw header on each page
    def draw_header(canvas, doc):
        canvas.saveState()
        # Header table top right
        table_data = [
            ['Invoice Date:', invoice_date],
            ['Invoice Number:', invoice_number],
            ['Postcard ID:', ''],
            [postcard_id, '']
        ]
        header_table = Table(table_data, colWidths=[4*cm, 6*cm])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        w, h = header_table.wrap(doc.width, doc.height)
        header_table.drawOn(canvas, doc.leftMargin + doc.width + doc.rightMargin - w, doc.height + doc.topMargin - h)
        canvas.restoreState()

    # Function to draw footer on each page
    def draw_footer(canvas, doc):
        canvas.saveState()
        footer_text = "Website: card4u.org | Email: info@card4u.org | Address: Card4U, Austr. 3, 96242 Sonnefeld, Germany | Ust-IdNr.: DE 357293884"
        p = Paragraph(footer_text, styles['Normal'])
        w, h = p.wrap(doc.width, doc.height)
        p.drawOn(canvas, doc.leftMargin + (doc.width - w) / 2, doc.bottomMargin)
        canvas.restoreState()

    # Story elements
    story = []

    # Spacer to position addresses at 45mm from top (45mm - 20mm topMargin = 25mm)
    story.append(Spacer(1, 2.5*cm))  # 25mm spacer

    # Letterhead - Sender address (20mm from left)
    story.append(Paragraph(f"<b>{sender_address}</b>", address_style))
    story.append(Spacer(1, 0.2*cm))

    # Separator line
    story.append(HLine(width=9*cm, thickness=0.5))
    story.append(Spacer(1, 0.2*cm))

    # If customer address is None, use delivery address
    if customer_address is None:
        customer_address = delivery_address

    # Customer address
    customer_address_html = customer_address.replace('\n', '<br/>')
    story.append(Paragraph(customer_address_html, address_style))
    story.append(Spacer(1, 2*cm))

    # Greeting
    name = customer_name if customer_name else "Customer"
    username = f"@{customer_username}" if customer_username else None
    if username and customer_email:
        email_part = f" ({username} - {customer_email})"
    elif username:
        email_part = f" ({username})"
    elif customer_email:
        email_part = f" ({customer_email})"
    else:
        email_part = ""
    greeting = f"Dear {name}{email_part} thank you for your order."
    story.append(Paragraph(greeting, styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    # Invoice title
    story.append(Paragraph("Invoice", title_style))
    story.append(Spacer(1, 0.2*cm))

    # Build items list
    shipping_description = 'International Postcard Postage' if is_international_shipping else 'National Postcard Postage'
    items = [
        {'description': 'Printing costs', 'amount': printing_costs},
        {'description': shipping_description, 'amount': shipping_cost},
    ]
    if voucher != 0.0:
        items.append({'description': 'Voucher', 'amount': voucher})

    # Items table
    table_data = [['Description', 'Amount (€)']]
    for item in items:
        table_data.append([
            item['description'],
            f"{item['amount']:.2f}".replace('.', ',')
        ])

    # Create table
    table = Table(table_data, colWidths=[10*cm, 3*cm])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(table)
    story.append(Spacer(1, 1*cm))

    # VAT summary
    summary_data = [
        [Paragraph('Included VAT in EUR (0%):', styles['Normal']), Paragraph('0,00', styles['Normal'])],
        [Paragraph('Included VAT in EUR (19%):', styles['Normal']), Paragraph(f"{vat_amount:.2f}".replace('.', ','), styles['Normal'])],
        [Paragraph('<b>Total Euro:</b>', styles['Normal']), Paragraph(f"<b>{total_amount:.2f}</b>".replace('.', ','), styles['Normal'])]
    ]

    summary_table = Table(summary_data, colWidths=[6*cm, 3*cm])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))

    # Wrap in a table to shift right
    outer_data = [['', summary_table]]
    outer_table = Table(outer_data, colWidths=[7.5*cm, 9*cm])
    outer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    story.append(outer_table)
    story.append(Spacer(1, 0.5*cm))

    # Delivery note
    delivery_address_html = delivery_address.replace('\n', '<br/>')
    delivery_text = f"""
    <b>The order has been shipped to the following address:</b><br/>
    {delivery_address_html}
    """
    story.append(Paragraph(delivery_text, styles['Normal']))

    # Function to draw both header and footer
    def draw_header_and_footer(canvas, doc):
        draw_header(canvas, doc)
        draw_footer(canvas, doc)

    # Build PDF with header and footer
    doc.build(story, onFirstPage=draw_header_and_footer, onLaterPages=draw_header_and_footer)

def main():
    """Example usage"""

    # Sample data
    sender_address = "Card4U, Austr. 3, 96242 Sonnefeld, Germany"
    customer_address = "Customer Name\nCustomer Street 456\n67890 Customer City"
    delivery_address = "Recipient Name\nDelivery Street 789\n01234 Delivery City"
    invoice_date = datetime.now().strftime('%Y-%m-%d')
    invoice_number = "C4U-2024-0001"
    postcard_id = "79733131-93d3-4a30-b2f1-6e0728e3bfb9"
    customer_name = "John Doe"
    customer_email = "john@example.com"
    customer_username = "johndoe"

    # Costs
    printing_costs = 0.54
    shipping_cost = 0.95
    voucher = -0.20
    is_international_shipping = True

    # Calculate VAT and total
    net = printing_costs + shipping_cost
    vat_amount = net * 0.19
    total_amount = net + vat_amount + voucher

    # Create PDF
    output_path = "rechnung.pdf"
    create_invoice_pdf(
        output_path,
        sender_address,
        customer_address,
        delivery_address,
        invoice_date,
        invoice_number,
        postcard_id,
        printing_costs,
        shipping_cost,
        voucher,
        is_international_shipping,
        customer_name,
        customer_email,
        customer_username,
        vat_amount,
        total_amount
    )

    print(f"Invoice created: {output_path}")

if __name__ == "__main__":
    main()