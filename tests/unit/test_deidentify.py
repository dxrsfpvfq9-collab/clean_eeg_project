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


# ---- panel_label: the Brain Panel's "Name:" line --------------------------
from files.deidentify import panel_label as p


def test_panel_masks_whole_name_then_keeps_30_char_tail():
    label = p(r"c:/inetpub/Practitioners\dr1/9999 Jordan Smithers 02.001.01 AGE 12  EO")
    assert label == "######## 02.001.01 AGE 12  EO"
    assert len(label) <= 30 and "Jordan" not in label and "Smithers" not in label


def test_panel_short_names_unchanged_and_no_leading_separator():
    assert p(r"C:\x\STLE qEEG 03.001.01 AGE 10 EC") == "STLE qEEG 03.001.01 AGE 10 EC"
    assert p(r"C:\x\raw_130399") == "raw_130399"
    assert p("c:/a/9999 - Jordan AB 04.000.02 AGE 9 EC") == "###### ## 04.000.02 AGE 9 EC"
