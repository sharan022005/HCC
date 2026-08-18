import os
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from backend.models import PatientDocument, PredictionRecord, LLMExplanation

def generate_patient_pdf(patient: dict, prediction: dict, explanation: dict) -> io.BytesIO:
    """Generates a PDF report for a given patient and returns it as a BytesIO buffer."""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=40)
                            
    Story = []
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#4318ff'),
        spaceAfter=14
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2b3674'),
        spaceAfter=10,
        spaceBefore=15
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 11
    normal_style.leading = 14
    
    # Title
    Story.append(Paragraph(f"HCC Gap Analysis Report", title_style))
    Story.append(Paragraph(f"Patient ID: {patient.get('_id', 'Unknown')}", normal_style))
    Story.append(Spacer(1, 20))
    
    # 1. Demographics
    Story.append(Paragraph("Demographics", heading_style))
    demo = patient.get('demographics', {})
    demo_data = [
        ["Age", str(demo.get('age', 'N/A'))],
        ["Gender", demo.get('gender', 'N/A')],
        ["Race", demo.get('race', 'N/A')],
        ["Ethnicity", demo.get('ethnicity', 'N/A')]
    ]
    t_demo = Table(demo_data, colWidths=[150, 250])
    t_demo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f4f7fe')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2b3674')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
    ]))
    Story.append(t_demo)
    Story.append(Spacer(1, 15))
    
    # 2. Risk Prediction
    Story.append(Paragraph("Prediction Summary", heading_style))
    
    risk_level = prediction.get('risk_level', 'Unknown')
    risk_color = colors.HexColor('#e2e8f0') # default
    if risk_level == "Potential Documentation Gap":
        risk_color = colors.HexColor('#fee2e2')
    elif risk_level == "Review Required":
        risk_color = colors.HexColor('#fef3c7')
    elif risk_level == "Supported Documentation":
        risk_color = colors.HexColor('#dcfce7')
        
    pred_data = [
        ["Model", prediction.get('model_name', 'XGBoost')],
        ["Risk Level", risk_level],
        ["Probability", f"{prediction.get('probability', 0):.2f}"],
        ["Date", prediction.get('prediction_date', 'Unknown')]
    ]
    
    t_pred = Table(pred_data, colWidths=[150, 250])
    t_pred.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f4f7fe')),
        ('BACKGROUND', (1, 1), (1, 1), risk_color), # highlight risk level
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2b3674')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
    ]))
    Story.append(t_pred)
    Story.append(Spacer(1, 15))
    
    # 3. Clinical History
    Story.append(Paragraph("Clinical History", heading_style))
    
    # Conditions
    conditions = patient.get('conditions', [])
    if conditions:
        Story.append(Paragraph("<b>Conditions</b>", normal_style))
        Story.append(Spacer(1, 5))
        cond_data = [["Date", "Description"]]
        for c in conditions:
            desc = c.get('DESCRIPTION') or c.get('CODE') or 'Unknown'
            date = c.get('START') or 'Unknown'
            cond_data.append([str(date), str(desc)])
            
        t_cond = Table(cond_data, colWidths=[100, 300])
        t_cond.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2b3674')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        Story.append(t_cond)
        Story.append(Spacer(1, 15))
        
    # Medications
    medications = patient.get('medications', [])
    if medications:
        Story.append(Paragraph("<b>Medications</b>", normal_style))
        Story.append(Spacer(1, 5))
        med_data = [["Date", "Description"]]
        for m in medications:
            desc = m.get('DESCRIPTION') or m.get('CODE') or 'Unknown'
            date = m.get('START') or 'Unknown'
            med_data.append([str(date), str(desc)])
            
        t_med = Table(med_data, colWidths=[100, 300])
        t_med.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2b3674')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        Story.append(t_med)
        Story.append(Spacer(1, 15))

    # 4. AI Explanation
    Story.append(Paragraph("AI Clinical Rationale", heading_style))
    exp_text = explanation.get('explanation', 'No explanation generated.')
    # Handle basic markdown to reportlab conversion (bolding)
    exp_text = exp_text.replace('**', '<b>', 1).replace('**', '</b>', 1) 
    
    # ReportLab Paragraph can handle basic HTML tags like <b> and <br/>
    # Replace markdown bold ** with <b>...</b>
    import re
    exp_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', exp_text)
    # Replace newlines with <br/>
    exp_text = exp_text.replace('\n', '<br/>')
    
    Story.append(Paragraph(exp_text, normal_style))
    
    # Generate PDF
    doc.build(Story)
    buffer.seek(0)
    return buffer

def generate_bulk_summary_pdf(patients_data: list) -> io.BytesIO:
    """Generates a bulk PDF report summarizing multiple patients."""
    buffer = io.BytesIO()
    # Landscape orientation is better for wide tables
    from reportlab.lib.pagesizes import letter, landscape
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            rightMargin=40, leftMargin=40,
                            topMargin=40, bottomMargin=40)
                            
    Story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#4318ff'),
        spaceAfter=14
    )
    
    Story.append(Paragraph("Filtered Patients Summary Report", title_style))
    Story.append(Spacer(1, 10))
    
    if not patients_data:
        Story.append(Paragraph("No patients found in this filter.", styles['Normal']))
        doc.build(Story)
        buffer.seek(0)
        return buffer
        
    table_data = [["Patient ID", "Age", "Gender", "Risk Level", "Probability", "Status"]]
    
    for p in patients_data:
        prob_str = f"{p.get('probability', 0)*100:.1f}%"
        table_data.append([
            str(p.get("patient_id", "Unknown")),
            str(p.get("age", "N/A")),
            str(p.get("gender", "N/A")),
            str(p.get("risk_level", "Unknown")),
            prob_str,
            str(p.get("review_status", "Pending"))
        ])
        
    t = Table(table_data, colWidths=[230, 50, 60, 150, 80, 100])
    
    # Base style
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2b3674')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]
    
    # Alternate row colors and risk colors
    for i in range(1, len(table_data)):
        risk = table_data[i][3]
        if risk == "Potential Documentation Gap":
            t_style.append(('BACKGROUND', (3, i), (3, i), colors.HexColor('#fee2e2')))
        elif risk == "Review Required":
            t_style.append(('BACKGROUND', (3, i), (3, i), colors.HexColor('#fef3c7')))
        elif risk == "Supported Documentation":
            t_style.append(('BACKGROUND', (3, i), (3, i), colors.HexColor('#dcfce7')))
            
        if i % 2 == 0:
            t_style.append(('BACKGROUND', (0, i), (2, i), colors.HexColor('#f8fafc')))
            t_style.append(('BACKGROUND', (4, i), (-1, i), colors.HexColor('#f8fafc')))
            
    t.setStyle(TableStyle(t_style))
    Story.append(t)
    
    doc.build(Story)
    buffer.seek(0)
    return buffer
