from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent


def build(source, target):
    document = Document()
    for element in document.styles.element.xpath('.//w:pBdr'):
        element.getparent().remove(element)
    section = document.sections[0]
    section.page_height = Inches(11.7)
    section.page_width = Inches(8.3)
    section.top_margin = section.bottom_margin = Inches(.7)
    section.left_margin = section.right_margin = Inches(.8)
    normal = document.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.1
    for name, size in [('Title', 26), ('Heading 1', 16), ('Heading 2', 13)]:
        style = document.styles[name]
        style.font.name = 'Calibri'
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(14)
        style.paragraph_format.space_after = Pt(7)
    code_style = document.styles.add_style('Command', 1)
    code_style.font.name = 'Consolas'
    code_style.font.size = Pt(9)
    code_style.paragraph_format.space_after = Pt(3)
    code_style.paragraph_format.keep_together = True
    lines = (ROOT / source).read_text(encoding='utf-8').splitlines()
    i = 0
    in_code = False
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            in_code = not in_code
        elif not line.strip():
            pass
        elif in_code:
            document.add_paragraph(line, 'Command')
        elif line.startswith('# '):
            document.add_paragraph(line[2:], 'Title')
        elif line.startswith('## '):
            document.add_paragraph(line[3:], 'Heading 1')
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                if not re.fullmatch(r'[| :\-]+', lines[i]):
                    rows.append([x.strip() for x in lines[i].strip('|').split('|')])
                i += 1
            i -= 1
            table = document.add_table(rows=0, cols=len(rows[0]))
            table.autofit = False
            widths = [1.85, 1.9, 2.9] if len(rows[0]) == 3 else [6.6 / len(rows[0])] * len(rows[0])
            for col, width in zip(table.columns, widths):
                col.width = Inches(width)
            for index, values in enumerate(rows):
                cells = table.add_row().cells
                for cell, value, width in zip(cells, values, widths):
                    cell.width = Inches(width)
                    cell.text = value
                    tcpr = cell._tc.get_or_add_tcPr()
                    margins = OxmlElement('w:tcMar')
                    for side in ['top','left','bottom','right']:
                        margin = OxmlElement('w:' + side)
                        margin.set(qn('w:w'), '95')
                        margin.set(qn('w:type'), 'dxa')
                        margins.append(margin)
                    tcpr.append(margins)
                    shading = OxmlElement('w:shd')
                    shading.set(qn('w:fill'), '17365D' if index == 0 else ('F1F4F7' if index % 2 else 'FFFFFF'))
                    tcpr.append(shading)
                    for p in cell.paragraphs:
                        p.paragraph_format.keep_with_next = index < len(rows) - 1
                        p.paragraph_format.space_after = Pt(3)
                        p.paragraph_format.line_spacing = 1
                        for run in p.runs:
                            run.font.size = Pt(10)
                            if index == 0:
                                run.bold = True
                                run.font.color.rgb = RGBColor(255,255,255)
                if index == 0:
                    repeat = OxmlElement('w:tblHeader')
                    table.rows[index]._tr.get_or_add_trPr().append(repeat)
            borders = OxmlElement('w:tblBorders')
            for side in ['top','left','bottom','right','insideH','insideV']:
                element = OxmlElement('w:' + side)
                element.set(qn('w:val'), 'single')
                element.set(qn('w:sz'), '5')
                element.set(qn('w:color'), 'D9D9D9')
                borders.append(element)
            table._tbl.tblPr.append(borders)
            document.add_paragraph().paragraph_format.space_after = Pt(1)
        else:
            document.add_paragraph(line)
        i += 1
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    run = footer.add_run()
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    run._r.addnext(field)
    document.core_properties.title = document.paragraphs[0].text
    document.core_properties.author = 'PACT Compute Project Team'
    document.save(ROOT / target)
    print(target, 'words', len(re.findall(r'\S+', (ROOT / source).read_text(encoding='utf-8'))))


build('implementation-report.md', 'PACT_Compute_Implementation_Report.docx')
build('teacher-demonstration-guide.md', 'PACT_Compute_Teacher_Demonstration_Guide.docx')
