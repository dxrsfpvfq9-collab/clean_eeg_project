"""files/deidentify.py -- names in study file names are masked on cascade pages."""
from files.deidentify import deidentify_label as d


def test_first_name_and_initial_masked():
    assert d("9999 Jordan D 01.000.03 AGE 15 EC") == "9999 ###### # 01.000.03 AGE 15 EC"


def test_directory_dropped_and_extension_removed():
    assert d(r"C:\Dropbox\Reviews\Smith Clinic\9999 Jordan D AGE 15 EC.edf") \
        == "9999 ###### # AGE 15 EC"
    assert d("c:/inetpub/Practitioners/JaneDoe/9999 Jordan D EC.edf") == "9999 ###### # EC"


def test_codes_and_technical_terms_kept():
    assert d("raw_130399") == "raw_130399"
    assert d("STLE qEEG 03.001.01 AGE 10 EC") == "STLE qEEG 03.001.01 AGE 10 EC"


def test_dotted_and_hyphenated_names():
    assert d("9998 Taylor B. EC") == "9998 ###### #. EC"
    assert d("Lena B EC.RECON") == "#### # EC.RECON"
    assert d("9996-Morgan EO") == "9996-###### EO"


def test_age_over_89_generalised():
    assert d("9997 Robin K AGE 93 EO") == "9997 ##### # AGE 90+ EO"
    assert d("9997 Robin K AGE 89 EO") == "9997 ##### # AGE 89 EO"
