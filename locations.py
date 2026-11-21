"""
Pakistan location reference data used by the rule-based validator (admin.py)
and by the application form dropdowns (form.html).

Structure:
    LOCATIONS[province][district] = [cities in that district]
    BRANCHES[branch value] = {"province": ..., "city": ...}

Keep this file as the single source of truth: the form builds its
Province -> District -> City dropdowns from it, and the server rejects any
combination that is not listed here.
"""

ICT = "Islamabad Capital Territory"

LOCATIONS = {
    "Punjab": {
        "Attock": ["Attock", "Hasan Abdal", "Fateh Jang", "Pindi Gheb", "Hazro", "Jand"],
        "Bahawalnagar": ["Bahawalnagar", "Chishtian", "Haroonabad", "Fort Abbas", "Minchinabad"],
        "Bahawalpur": ["Bahawalpur", "Ahmadpur East", "Hasilpur", "Khairpur Tamewali", "Yazman"],
        "Bhakkar": ["Bhakkar", "Darya Khan", "Kallur Kot", "Mankera"],
        "Chakwal": ["Chakwal", "Choa Saidan Shah", "Kallar Kahar"],
        "Chiniot": ["Chiniot", "Bhowana", "Lalian"],
        "Dera Ghazi Khan": ["Dera Ghazi Khan", "Kot Chutta"],
        "Faisalabad": ["Faisalabad", "Jaranwala", "Samundri", "Tandlianwala", "Chak Jhumra"],
        "Gujranwala": ["Gujranwala", "Kamoke", "Nowshera Virkan"],
        "Gujrat": ["Gujrat", "Kharian", "Sarai Alamgir", "Lalamusa", "Jalalpur Jattan"],
        "Hafizabad": ["Hafizabad", "Pindi Bhattian"],
        "Jhang": ["Jhang", "Shorkot", "Ahmedpur Sial", "Athara Hazari"],
        "Jhelum": ["Jhelum", "Dina", "Pind Dadan Khan", "Sohawa"],
        "Kasur": ["Kasur", "Chunian", "Pattoki", "Kot Radha Kishan"],
        "Khanewal": ["Khanewal", "Kabirwala", "Mian Channu", "Jahanian"],
        "Khushab": ["Khushab", "Jauharabad", "Noorpur Thal", "Quaidabad"],
        "Kot Addu": ["Kot Addu", "Chowk Sarwar Shaheed"],
        "Lahore": ["Lahore", "Raiwind"],
        "Layyah": ["Layyah", "Karor Lal Esan", "Chaubara"],
        "Lodhran": ["Lodhran", "Dunyapur", "Kahror Pacca"],
        "Mandi Bahauddin": ["Mandi Bahauddin", "Malakwal", "Phalia"],
        "Mianwali": ["Mianwali", "Isa Khel", "Piplan"],
        "Multan": ["Multan", "Shujabad", "Jalalpur Pirwala"],
        "Murree": ["Murree", "Kotli Sattian"],
        "Muzaffargarh": ["Muzaffargarh", "Alipur", "Jatoi"],
        "Nankana Sahib": ["Nankana Sahib", "Shahkot", "Sangla Hill"],
        "Narowal": ["Narowal", "Shakargarh", "Zafarwal"],
        "Okara": ["Okara", "Depalpur", "Renala Khurd"],
        "Pakpattan": ["Pakpattan", "Arifwala"],
        "Rahim Yar Khan": ["Rahim Yar Khan", "Sadiqabad", "Khanpur", "Liaquatpur"],
        "Rajanpur": ["Rajanpur", "Jampur", "Rojhan"],
        "Rawalpindi": ["Rawalpindi", "Taxila", "Gujar Khan", "Kahuta", "Kallar Syedan"],
        "Sahiwal": ["Sahiwal", "Chichawatni"],
        "Sargodha": ["Sargodha", "Bhalwal", "Kot Momin", "Sillanwali", "Shahpur", "Bhera"],
        "Sheikhupura": ["Sheikhupura", "Muridke", "Ferozewala", "Safdarabad"],
        "Sialkot": ["Sialkot", "Daska", "Sambrial", "Pasrur"],
        "Talagang": ["Talagang", "Lawa"],
        "Taunsa": ["Taunsa"],
        "Toba Tek Singh": ["Toba Tek Singh", "Gojra", "Kamalia", "Pir Mahal"],
        "Vehari": ["Vehari", "Burewala", "Mailsi"],
        "Wazirabad": ["Wazirabad", "Alipur Chatha"],
    },
    "Sindh": {
        "Badin": ["Badin", "Matli", "Talhar", "Tando Bago"],
        "Dadu": ["Dadu", "Mehar", "Khairpur Nathan Shah", "Johi"],
        "Ghotki": ["Ghotki", "Mirpur Mathelo", "Daharki", "Ubauro"],
        "Hyderabad": ["Hyderabad", "Latifabad", "Qasimabad"],
        "Jacobabad": ["Jacobabad", "Thul"],
        "Jamshoro": ["Jamshoro", "Kotri", "Sehwan", "Manjhand"],
        "Karachi Central": ["Karachi"],
        "Karachi East": ["Karachi"],
        "Karachi South": ["Karachi"],
        "Karachi West": ["Karachi"],
        "Keamari": ["Karachi"],
        "Korangi": ["Karachi"],
        "Malir": ["Karachi"],
        "Kashmore": ["Kashmore", "Kandhkot", "Tangwani"],
        "Khairpur": ["Khairpur", "Gambat", "Kot Diji", "Thari Mirwah"],
        "Larkana": ["Larkana", "Ratodero", "Dokri"],
        "Matiari": ["Matiari", "Hala", "Saeedabad"],
        "Mirpur Khas": ["Mirpur Khas", "Digri", "Kot Ghulam Muhammad"],
        "Naushahro Feroze": ["Naushahro Feroze", "Moro", "Kandiaro", "Mehrabpur"],
        "Qambar Shahdadkot": ["Qambar", "Shahdadkot", "Warah"],
        "Sanghar": ["Sanghar", "Shahdadpur", "Tando Adam"],
        "Shaheed Benazirabad": ["Nawabshah", "Sakrand", "Daur"],
        "Shikarpur": ["Shikarpur", "Garhi Yasin", "Lakhi"],
        "Sujawal": ["Sujawal", "Jati"],
        "Sukkur": ["Sukkur", "Rohri", "Pano Aqil", "Saleh Pat"],
        "Tando Allahyar": ["Tando Allahyar", "Chamber", "Jhando Mari"],
        "Tando Muhammad Khan": ["Tando Muhammad Khan", "Bulri Shah Karim"],
        "Tharparkar": ["Mithi", "Islamkot", "Chachro", "Diplo"],
        "Thatta": ["Thatta", "Makli", "Mirpur Sakro", "Gharo"],
        "Umerkot": ["Umerkot", "Kunri", "Pithoro"],
    },
    "Khyber Pakhtunkhwa": {
        "Abbottabad": ["Abbottabad", "Havelian", "Nathia Gali"],
        "Bajaur": ["Khar"],
        "Bannu": ["Bannu"],
        "Battagram": ["Battagram"],
        "Buner": ["Daggar"],
        "Charsadda": ["Charsadda", "Tangi", "Shabqadar"],
        "Dera Ismail Khan": ["Dera Ismail Khan", "Paharpur", "Kulachi"],
        "Hangu": ["Hangu"],
        "Haripur": ["Haripur", "Khanpur", "Ghazi"],
        "Karak": ["Karak", "Takht-e-Nasrati"],
        "Khyber": ["Landi Kotal", "Jamrud", "Bara"],
        "Kohat": ["Kohat"],
        "Kolai Palas": ["Palas"],
        "Kurram": ["Parachinar"],
        "Lakki Marwat": ["Lakki Marwat"],
        "Lower Chitral": ["Chitral", "Drosh"],
        "Upper Chitral": ["Booni", "Mastuj"],
        "Lower Dir": ["Timergara"],
        "Upper Dir": ["Dir"],
        "Lower Kohistan": ["Pattan"],
        "Upper Kohistan": ["Dasu"],
        "Lower South Waziristan": ["Wana"],
        "Upper South Waziristan": ["Ladha"],
        "Malakand": ["Batkhela", "Dargai"],
        "Mansehra": ["Mansehra", "Balakot", "Oghi"],
        "Mardan": ["Mardan", "Takht Bhai"],
        "Mohmand": ["Ghallanai"],
        "North Waziristan": ["Miranshah", "Mir Ali"],
        "Nowshera": ["Nowshera", "Pabbi", "Risalpur"],
        "Orakzai": ["Kalaya"],
        "Peshawar": ["Peshawar"],
        "Shangla": ["Alpuri", "Besham"],
        "Swabi": ["Swabi", "Topi", "Lahor"],
        "Swat": ["Mingora", "Saidu Sharif", "Matta", "Kalam", "Khwazakhela"],
        "Tank": ["Tank"],
        "Torghar": ["Judba"],
    },
    "Balochistan": {
        "Awaran": ["Awaran"],
        "Barkhan": ["Barkhan"],
        "Chagai": ["Dalbandin", "Nok Kundi", "Taftan"],
        "Chaman": ["Chaman"],
        "Dera Bugti": ["Dera Bugti", "Sui"],
        "Duki": ["Duki"],
        "Gwadar": ["Gwadar", "Pasni", "Ormara", "Jiwani"],
        "Harnai": ["Harnai"],
        "Hub": ["Hub"],
        "Jafarabad": ["Dera Allah Yar"],
        "Jhal Magsi": ["Jhal Magsi", "Gandava"],
        "Kachhi": ["Dhadar", "Bhag"],
        "Kalat": ["Kalat"],
        "Kech": ["Turbat"],
        "Kharan": ["Kharan"],
        "Khuzdar": ["Khuzdar", "Wadh"],
        "Killa Abdullah": ["Killa Abdullah", "Gulistan"],
        "Killa Saifullah": ["Killa Saifullah"],
        "Kohlu": ["Kohlu"],
        "Lasbela": ["Uthal", "Bela"],
        "Loralai": ["Loralai"],
        "Mastung": ["Mastung"],
        "Musakhel": ["Musakhel"],
        "Nasirabad": ["Dera Murad Jamali"],
        "Nushki": ["Nushki"],
        "Panjgur": ["Panjgur"],
        "Pishin": ["Pishin"],
        "Quetta": ["Quetta"],
        "Sherani": ["Sherani"],
        "Sibi": ["Sibi"],
        "Sohbatpur": ["Sohbatpur"],
        "Surab": ["Surab"],
        "Usta Muhammad": ["Usta Muhammad"],
        "Washuk": ["Washuk"],
        "Zhob": ["Zhob"],
        "Ziarat": ["Ziarat"],
    },
    ICT: {
        "Islamabad": ["Islamabad"],
    },
    "Gilgit-Baltistan": {
        "Astore": ["Astore"],
        "Diamer": ["Chilas"],
        "Ghanche": ["Khaplu"],
        "Ghizer": ["Gahkuch"],
        "Gilgit": ["Gilgit"],
        "Hunza": ["Aliabad", "Karimabad"],
        "Kharmang": ["Tolti"],
        "Nagar": ["Nagar"],
        "Shigar": ["Shigar"],
        "Skardu": ["Skardu"],
    },
    "Azad Jammu & Kashmir": {
        "Bagh": ["Bagh"],
        "Bhimber": ["Bhimber", "Samahni"],
        "Hattian Bala": ["Hattian Bala"],
        "Haveli": ["Forward Kahuta"],
        "Kotli": ["Kotli"],
        "Mirpur": ["Mirpur", "Dadyal"],
        "Muzaffarabad": ["Muzaffarabad"],
        "Neelum": ["Athmuqam"],
        "Poonch": ["Rawalakot"],
        "Sudhnoti": ["Pallandri"],
    },
}

PROVINCES = list(LOCATIONS.keys())

# Alternate spellings people (or older form versions) may send.
PROVINCE_ALIASES = {
    "punjab": "Punjab",
    "sindh": "Sindh",
    "kpk": "Khyber Pakhtunkhwa",
    "kp": "Khyber Pakhtunkhwa",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "balochistan": "Balochistan",
    "baluchistan": "Balochistan",
    "islamabad": ICT,
    "ict": ICT,
    "islamabad capital territory": ICT,
    "federal capital": ICT,
    "federal capital territory": ICT,
    "gilgit-baltistan": "Gilgit-Baltistan",
    "gilgit baltistan": "Gilgit-Baltistan",
    "gb": "Gilgit-Baltistan",
    "azad jammu & kashmir": "Azad Jammu & Kashmir",
    "azad jammu and kashmir": "Azad Jammu & Kashmir",
    "azad kashmir": "Azad Jammu & Kashmir",
    "ajk": "Azad Jammu & Kashmir",
    "ak": "Azad Jammu & Kashmir",
}

# Branch value (must match the keys in branches.json) -> where it is.
# "city" is only used as the dropdown group label.
BRANCHES = {
    # Islamabad Capital Territory
    "G-8/1 Mauve Area Islamabad": {"province": ICT, "city": "Islamabad"},
    "13-C, Al-Hussain Plaza, G-10 Markaz, Islamabad": {"province": ICT, "city": "Islamabad"},
    "Plot 19-A, Pak Plaza, Fazal-e-Haq Road, Blue Area, Islamabad": {"province": ICT, "city": "Islamabad"},
    "OPF Head Office Building, 2 Shahrah-e-Jamhuriat, G-5, Islamabad": {"province": ICT, "city": "Islamabad"},
    # Punjab
    "4-A, Sher Shah Block, Behind Barkat Market, New Garden Town Lahore": {"province": "Punjab", "city": "Lahore"},
    "8-A, Shahrah-e-Aewan Tijarat, Shadman, Lahore": {"province": "Punjab", "city": "Lahore"},
    "14-kilometer, Main Raiwind Road, Araiyan Morr, Lahore": {"province": "Punjab", "city": "Lahore"},
    "27-xx phase 3, DHA, Khayaban e Iqbal Road, Lahore": {"province": "Punjab", "city": "Lahore"},
    "Saeed Park, near Ravi Toll Plaza, Shahdara, Lahore": {"province": "Punjab", "city": "Lahore"},
    "Lahore High Court Bar Association": {"province": "Punjab", "city": "Lahore"},
    "Lahore Chamber of Commerce and Industry": {"province": "Punjab", "city": "Lahore"},
    "Opposite Station High School No.3, Gunjmandi More Rawalpindi": {"province": "Punjab", "city": "Rawalpindi"},
    "Near Rehman Abad, Murree Road, Rawalpindi": {"province": "Punjab", "city": "Rawalpindi"},
    "Jail Road, opposite Allied Hospital, Faisalabad": {"province": "Punjab", "city": "Faisalabad"},
    "Fazal Plaza behind Kohinoor Plaza, Jaranwala Road Faisalabad": {"province": "Punjab", "city": "Faisalabad"},
    "Near Madni Chowk, U-Block, New Multan Colony": {"province": "Punjab", "city": "Multan"},
    "Third Floor, Chen One Tower, Abdali Road, Multan": {"province": "Punjab", "city": "Multan"},
    "Zeeshan Housing Complex, Kashmir Road, Sialkot": {"province": "Punjab", "city": "Sialkot"},
    "Haji Pura Rd, Muslim Colony Sialkot": {"province": "Punjab", "city": "Sialkot"},
    # Sindh
    "Shahrah-e-Iraq, Saddar Karachi": {"province": "Sindh", "city": "Karachi"},
    "1st Floor, EOBI House, Sharah-e-Faisal Karachi": {"province": "Sindh", "city": "Karachi"},
    "Behind South City Hospital, Clifton 3 Karachi": {"province": "Sindh", "city": "Karachi"},
    "Near Nehal Hospital, Kala Board Karachi": {"province": "Sindh", "city": "Karachi"},
    "Karsaz Faisal Cantonment Karachi": {"province": "Sindh", "city": "Karachi"},
    # Khyber Pakhtunkhwa
    "Phase-5, near North West Hospital, Hayatabad Peshawar": {"province": "Khyber Pakhtunkhwa", "city": "Peshawar"},
    "Nadra Mega Centre Tambowanu Mor Peshawar": {"province": "Khyber Pakhtunkhwa", "city": "Peshawar"},
    "DHQ Hospital Road, Phase II, KDA Township Kohat": {"province": "Khyber Pakhtunkhwa", "city": "Kohat"},
    "Near Agriculture Research Center, Main Bannu Road D.I.Khan": {"province": "Khyber Pakhtunkhwa", "city": "Dera Ismail Khan"},
    "Kanju Township, Saidu Sharif Swat": {"province": "Khyber Pakhtunkhwa", "city": "Swat"},
    "House No. 878, Near PC Hotel, Mansehra Road Abbottabad": {"province": "Khyber Pakhtunkhwa", "city": "Abbottabad"},
    # Balochistan
    "Arbab Barkat Ali Road, Near Railway Football Ground Quetta": {"province": "Balochistan", "city": "Quetta"},
    "Plot No. 30, Jinnah Town Quetta": {"province": "Balochistan", "city": "Quetta"},
    "House # A/78, near Wapda Office, Cantonment Zhob": {"province": "Balochistan", "city": "Zhob"},
    "TTC Colony Ward Gwadar": {"province": "Balochistan", "city": "Gwadar"},
    "Makran Plaza, Infront of NADRA Office Turbat": {"province": "Balochistan", "city": "Turbat"},
    # Gilgit-Baltistan
    "Near Shell Pump, Krasmathang Olding Road Skardu": {"province": "Gilgit-Baltistan", "city": "Skardu"},
    "Muhalla Qazilbash, Near Yadgar Chowk Gilgit": {"province": "Gilgit-Baltistan", "city": "Gilgit"},
    "District Diamir, Khasra No. 426 Harpan Chillas": {"province": "Gilgit-Baltistan", "city": "Chilas"},
    # Azad Jammu & Kashmir
    "Mir Plaza Bela Noor Shah, near Bus Stand Muzaffarabad": {"province": "Azad Jammu & Kashmir", "city": "Muzaffarabad"},
    "Near Bhutto park, near PC Hotel Mirpur": {"province": "Azad Jammu & Kashmir", "city": "Mirpur"},
    "Near DC Office, G & A Plaza, Pindi Road Kotli": {"province": "Azad Jammu & Kashmir", "city": "Kotli"},
}


def normalize_province(value):
    """Return the canonical province name, or None if it isn't one."""
    if not value:
        return None
    v = value.strip()
    if v in LOCATIONS:
        return v
    return PROVINCE_ALIASES.get(v.lower())


def allowed_branch_provinces(province):
    """Branches an applicant may pick: their own province, plus Islamabad."""
    return {province, ICT}
