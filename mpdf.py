# Use this (for fpdf2):
from fpdf import FPDF 
from barcode.codex import Code128 # barcode by name generate barcode of any name and code 128 is a type of barcode that only contains numbers
from barcode.writer import ImageWriter # to convert barcode into image
import qrcode    # by name generate qrcode
import io         # to convert qrcode into image or into bytes so that img cant be stored locally and can be used directly in pdf
from io import BytesIO    # convet data into bytes so that it can be sent as file without saving locally
from PIL import Image   # to handle image operations but we didnt use it
from datetime import datetime # to get date and time
from timeslot import time_slot


def makepdf(token, name, dob, age, CNIC,email, Address, City, Domicile, province, District, branch, *,    
    father_cnic=None,
    mother_cnic=None,
    parent_cnic=None):    

    a = token                            
  
    class PDF(FPDF):
        def header(self):
            try:
                self.image('static/images/logo.jpeg', 10, 8, 33)
            except:
                pass
            try:
                self.image('static/images/logo 2.jpeg', 160, 8, 43)
            except:
                pass
            self.set_font('Arial', 'BI', 20)
            self.cell(0, 70, "Directorate General of Immigration & Passports", border=0, ln=1, align='C')
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'This is a computer generated document doesnot require any stamp or signature', 0, 0, 'C')

        def draw_checkbox(self, x, y, size=4, checked=False):
            self.rect(x, y, size, size)
            if checked:
                self.line(x+1, y+size/2, x+size/2, y+size-1)
                self.line(x+size/2, y+size-1, x+size-1, y+1)

    # class pdf and its object pdf   
    pdf = PDF('p', 'mm', 'A4')
    pdf.add_page() # add a page

    pdf.set_font("Arial", "B", size=20) # set font of pdf
    pdf.cell(100, -10, f"TOKEN #{a:03}", ln=0, align='C') # cell is like div in html it have width height and text and ln is like br in html if ln=1 it will go to next line after this cell if 0 it will stay in same line

    token_str = f"{a:03}" # token number fromating
    try:
        barcode = Code128(token_str, writer=ImageWriter()) # heres the fun part token str have the token number and code128 converts it into barcode
        barcode_buffer = BytesIO() #but we dont want to save it locally so we use BytesIO to convert it into bytes
        
        # Write with options to prevent text rendering issues (FIX for rfind error)
        barcode.write(barcode_buffer, options={
            'module_height': 15,
            'module_width': 0.2,
            'quiet_zone': 1,
            'text_distance': 5,
            'font_size': 10,
            'write_text': True
        }) # write method writes the barcode into the buffer
        
        barcode_buffer.seek(0) # seek(0) moves the cursor to the beginning of the buffer so that we can read it from the start
        pdf.image(barcode_buffer, x=120, y=pdf.get_y()-14, w=60, h=30) # and voila we have barcode in pdf by using pdf.image method
    except Exception as e:
        print(f"Barcode generation error: {e}")

    pdf.ln(10) # cretaed space after barcode

    pdf.set_font("Arial", "B", size=14) 
    pdf.cell(0, 6, "Personal Details:", ln=1, align='L')

    pdf.set_font("Arial", size=11)  
    pdf.ln(2)

    # Create QR code but position it AFTER the details
    qr_buffer = None
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(CNIC)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
    except Exception as e:
        print(f"QR code generation error: {e}")

    pdf.set_font("Arial", size=12)
    
    times = time_slot(token)
   
    details = [
        ("Applicant Name", name),
        ("Date of Birth", dob),
        ("Age", str(age)),
        ("CNIC", CNIC),
        ("Email", email),
        ("Address", Address),
        ("Province", province),
        ("District", District),
        ("City", City),
        ("Domicile", Domicile),
        ("Date of Issue", datetime.now().strftime('%Y-%m-%d')),
        ("Issued Time", times),
        ("Branch", branch)
    ]
    
    # Print details in a clean format 
    for label, value in details:
        pdf.cell(35, 7, f"{label}:", border=0, align='L')  
        pdf.cell(120, 7, str(value), border=0, ln=1, align='L')  
    
    #adding QR code in the right position without overlapping with the personal details
    if qr_buffer:
        pdf.image(qr_buffer, x=125, y=pdf.get_y()-70, w=50, h=50) # smaller QR code

    pdf.ln(3)     

    # to check if user in under 18 
    is_minor = int(age) < 18

     # adding section for parental confirmation
    if is_minor:          
        pdf.set_font("Arial", "B", size=14)
        pdf.cell(0, 10, "Parental Confirmation for (Under 18 only):", ln=1, align='L')

        pdf.set_font("Arial", size=12)
        pdf.ln(5)

        # Parent details 
        father_cnic_display = father_cnic if father_cnic else 'N/A'
        mother_cnic_display = mother_cnic if mother_cnic else 'N/A'
        primary_guardian = parent_cnic if parent_cnic else (father_cnic if father_cnic else mother_cnic)
        
        # formatting for parent details
        
        pdf.cell(40, 8, "Father CNIC:", border=0, align='L')
        pdf.cell(80, 8, father_cnic_display, border=0, ln=1, align='L')

        pdf.cell(40, 8, "Mother CNIC:", border=0, align='L')
        pdf.cell(80, 8, mother_cnic_display, border=0, ln=1, align='L')

        pdf.cell(40, 8, "Primary Guardian:", border=0, align='L')
        pdf.cell(80, 8, primary_guardian if primary_guardian else 'N/A', border=0, ln=1, align='L')

        pdf.ln(5)

        #checkbox section for parents consent
        current_y = pdf.get_y()

        # drawing checkbox for under 18
        pdf.draw_checkbox(15, current_y, size=4, checked=True)
        pdf.set_xy(25, current_y-1)
        pdf.cell(0, 8, "Parental Consent Confirmed for Minors", ln=1, align='L')

        pdf.ln(2)
        current_y = pdf.get_y()
        pdf.draw_checkbox(15, current_y, size=4, checked=True)
        pdf.set_xy(25, current_y-1)
        pdf.cell(0, 6, "Parents/Guardian CNIC verified", ln=1, align='L')

        pdf.ln(2)
        current_y = pdf.get_y()
        pdf.draw_checkbox(15, current_y, size=4, checked=True)
        pdf.set_xy(25, current_y-1)
        pdf.cell(0, 6, "All required documents for minor submitted", ln=1, align='L')

        pdf.ln(5)

        # this section is added for physical signature of parent when they will print the pdf
        pdf.set_font("Arial", "B", size=11) # smaller font
        pdf.cell(0, 6, "Parent/Guardian Signature: ________________________", ln=1, align='L')
        pdf.ln(5)

    else:
        # For adults(18 or 18+), parental confirmation is not required
        pdf.set_font("Arial", "B", size=11) # smaller font
        pdf.cell(0, 6, "Parental Confirmation: ", ln=1, align='L')

        pdf.set_font("Arial", size=11) # smaller font
        pdf.ln(2)
        current_y = pdf.get_y()

        # drawing unchecked box for adults
        pdf.draw_checkbox(15, current_y, size=4, checked=False)
        pdf.set_xy(25, current_y-1)
        pdf.cell(0, 6, "NOT APPLICABLE (Applicant is 18 or older)", ln=1, align='L')
        pdf.ln(5)

    pdf.add_page() # Start instructions on new page
    
    pdf.set_font("Arial", "B", size=12) # smaller font
    pdf.cell(0, 6, "Important Instructions:", ln=1, align='L')

    pdf.set_font("Arial", size=10) # smaller font for instructions # smaller font for instructions
    pdf.ln(2)

    instructions = [
        "-> Personal appearance is mandatory for all applicants",
        "-> Arrive at your scheduled appointment time exactly",
        "-> Bring all original documents along with photocopies",
        "-> Valid CNIC/NICOP is mandatory for verification",
        "-> Incomplete applications will not be entertained",
        "-> Office timings are from 8:00 AM to 2:00 PM (varies by location)",
        "-> Token is valid only for the date of issue",
        "-> Late arrivals may result in appointment cancellation",
        "-> Keep this token receipt safe until completion of process"
    ]
    
    documents_required = [
        "-> Original valid CNIC/NICOP/Smart Card with 2 photocopies",
        "-> Previous Pakistani passport (if any) with photocopies of first 4 pages",
        "-> NOC from government department (for government employees issued within 90 days)",
        "-> Foreign passport with photocopy (for dual nationality holders only)",
        "-> Police report for lost passport mentioning previous passport number",
        "-> Birth certificate for minors (original and photocopy)",
        "-> Parents' CNICs and passports (for applicants under 18)",
        "-> For Married Females CNIC/NICOP must contain husband's name reflecting current marital status",
        "-> Marriage certificate if name change is required"
    ]
    
    for_minors = [
        "-> Child Registration Certificate (B-From) or B-Form from NADRA",
        "-> Both parents must be present (mandatory)",
        "-> NOC from absent parent (notarized) if one parent cannot attend",
        "-> Court guardianship certificate (in case of divorced/separated parents)",
        "-> Original death certificate (if one parent is deceased)"
    ]

    collection_instructions = [
        "-> Bring original receipt for passport collection",
        "-> Only blood relatives can collect on behalf of applicant (with written authorization)",
        "-> Previous passport must be surrendered during collection",
        "-> Collection hours: Monday-Friday 2:00-4:00 PM (varies by location)"
    ]
    
    processing_timeline = [
        "-> Normal processing: 21 working days",
        "-> Urgent processing: 5 working days",
        "-> Fast track: 2 working days (available in 47 cities)"
    ]
    
    additional_guidelines = [
        "-> Fingerprints must be clear - no henna, ink or coloring on fingers",
        "-> Both ears must be visible during photograph capture",
        "-> No endorsement of children's names allowed on parent's MRP",
        "-> Government employees need NOC issued within last 90 days",
        "-> First-time passport applicants may require security verification (3-6 months)",
        "-> Staple photocopies in prescribed order as instructed by office"
    ]

    # adding important istructions for minors
    

    for instruction in instructions:
        pdf.cell(0, 5, instruction, ln=1, align='L') # smaller height for instructions
     
    pdf.set_font("Arial", "B", size=12)   
    pdf.cell(0, 6, "Documents Required:", ln=1, align='L')  

    pdf.set_font("Arial", size=10) # smaller font for instructions
    pdf.ln(2)
    for instruction in documents_required:
        pdf.cell(0, 5, instruction, ln=1, align='L') # smaller height for instructions
    
    if is_minor:
        pdf.set_font("Arial", "B", size=12)   
        pdf.cell(0, 6, "Additional Documents for Minors:", ln=1, align='L')
        pdf.set_font("Arial", size=10) # smaller font for instructions
        pdf.ln(2)
        for instruction in for_minors:
            pdf.cell(0, 5, instruction, ln=1, align='L')
    
    pdf.set_font("Arial", "B", size=12)   
    pdf.cell(0, 6, "Additional Guide-lines:", ln=1, align='L')  

    pdf.set_font("Arial", size=10) # smaller font for instructions
    pdf.ln(2)
    for instruction in additional_guidelines:
        pdf.cell(0, 5, instruction, ln=1, align='L') 
        
    pdf.set_font("Arial", "B", size=12)   
    pdf.cell(0, 6, "Processing Time-Line:", ln=1, align='L')  

    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    for instruction in processing_timeline:
        pdf.cell(0, 5, instruction, ln=1, align='L')
        
    pdf.set_font("Arial", "B", size=12)   
    pdf.cell(0, 6, "Collection Instructions:", ln=1, align='L')  

    pdf.set_font("Arial", size=10)
    pdf.ln(2)
    for instruction in collection_instructions:
        pdf.cell(0, 5, instruction, ln=1, align='L')
    
    pdf_bytes = pdf.output() # Get PDF as bytes (dest="S" is default in fpdf2)
    
    buffer = BytesIO(pdf_bytes) # converting bytes into BytesIO buffer
    buffer.seek(0) # moving cursor to start of buffer
    return buffer # returning the buffer so that it can be used in app.py