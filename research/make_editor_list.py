# -*- coding: utf-8 -*-
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from docx_build import build

B = []
def H(t, l=1): B.append({"type":"heading","text":t,"level":l})
def P(t): B.append({"type":"para","segs":t})
def BU(t): B.append({"type":"bullet","segs":t})
def SP(): B.append({"type":"spacer"})

B.append({"type":"title","text":"Author Corrections to Proofs"})
B.append({"type":"subtitle","text":"Manuscript AIA62026679 — “Using Machine Learning to Enhance the EEG "
          "Screening Review by Pre-Screening the EEG” (Collura, Rosace, Turner, Ims & Brubaker)"})
SP()
P("The following corrections are listed in manuscript order. Each entry gives the location, the "
  "current text, the correction, and the reason. Priority key: [Critical] = factual or numerical "
  "error; [Error] = grammar or spelling; [Consistency] = standardization. The two highest-priority "
  "items are the specificity range (Item 5) and the metric count (Item 1), both of which are "
  "verifiable against Table 4 and Appendix A respectively.")

H("Critical — factual / numerical", 2)

P("1. Metric count (Abstract-area, §3.4, §3.5, §4.1, Future Works). "
  "The text states “46 … metrics” throughout, but Appendix A lists 48 metrics and the "
  "per-category counts in §3.4 indicate 48 (PDR “peak frequency” is counted both as the "
  "tenth PDR metric and as the “Alpha Peak” phenotype). Claude’s chart in Table 3 also "
  "says 48. Correction: change all “46” to “48,” and amend §3.4 “PDR Metrics: "
  "Ten metrics” to “Nine” (or drop peak frequency from the PDR list, since it is defined "
  "under Phenotypes).")

P("2. Electrode list (§3.2.3). The text says “all 19 standard scalp sites” but lists only "
  "17 — P3 and P4 are missing from (Fp1, Fp2, F3, F4, F7, F8, T3, T4, T5, T6, C3, C4, Fz, Cz, Pz, "
  "O1, O2). Add P3 and P4.")

P("3. FFT frequency range. Methods (§3.3.3 and §3.6) specify 0–70 Hz, but Appendix A says "
  "0–64 Hz. Reconcile to a single value.")

P("4. K–S test logic (§4.1). “… to demonstrate our ability to reject the null "
  "hypothesis and assert these samples conform to a Gaussian distribution.” For a K–S "
  "goodness-of-fit test, high p-values mean one FAILS to reject the null (that the data are Gaussian). "
  "As written it is self-contradictory and inconsistent with §3.5. Suggested: “… to "
  "demonstrate that the null hypothesis cannot be rejected, supporting the conclusion that these "
  "samples conform to a Gaussian distribution.”")

P("5. Specificity range (§4.1 twice, Discussion §5, and Table 5). The text repeatedly states "
  "“specificities of 79–91%.” Per Table 4 the specificity values are 76, 79, 83, 88, 84, "
  "88 — the correct range is 76–88%. Sensitivity (89–95%) and accuracy (78–91%) are "
  "correct. Must be corrected at every occurrence, including the Brain Panel row of Table 5.")

P("6. Citation numbers (Discussion §5 and Conclusion §6). “SCORE-AI (88.3% accuracy … "
  "[26])” — SCORE-AI is Tveit et al., reference [24] (ref [26] is Lemoine/DeepEpilepsy); "
  "correct to [24] (two occurrences). “IED detectors (82.5% sensitivity at 99% specificity "
  "[25])” — those figures are Tjepkema-Cloostermans, reference [23] (ref [25] is van Stigt); "
  "correct to [23]. Recommend a full pass over in-text citation numbers against the final reference list.")

P("7. “Five categories of neurometrics” (§4.1, Figure 4 discussion). §3.4 defines six "
  "non-statistical categories (PDR, Phenotypes, Focal, Frontal, Diffuse, State Shifts). Change "
  "“five” to “six,” or clarify the grouping.")

H("Errors — grammar / spelling", 2)

P("8. Broken sentence (typesetter query AQ6, §5). “… In conjunction with the diffuse "
  "amplitudes, and the total number of OOB metrics, provides a useful indicator …” has no "
  "subject. Rewrite: “It, in conjunction with the diffuse amplitudes and the total number of OOB "
  "metrics, provides a useful indicator …”")

P("9. Missing word (§4.1, p.8). “The 0.1 Hz high resolution of the FFT allows to more "
  "accurately point out changes …” → “allows us to more accurately point out.”")

P("10. “Kolmogorov–Smirnoff” (§4.1) is misspelled; the rest of the paper correctly "
  "uses “Smirnov.” Two instances on that line.")

P("11. “SIRI” (§1 Introduction) → “Siri.”")

P("12. “mean-μ and standard deviation-σ” (§3.5) reads oddly; use “mean "
  "(μ) and standard deviation (σ).”")

P("13. Reference [4]: the DOI ends with a stray tag “… 15500594241308654[4]” — "
  "delete the trailing “[4].”")

P("14. Reference [19]: “Seizure:. European Journal of Epilepsy” — remove the period after "
  "the colon (“Seizure: European Journal of Epilepsy”).")

H("Consistency", 2)

P("15. Citation style (§4.1). “corroborating prior findings (Collura & Tarrant, 2020)” is "
  "the only author-year citation in an otherwise numbered-citation paper — change to [7].")

P("16. AI-platform capitalization. Both “GROK”/“Grok” and "
  "“CLAUDE”/“Claude” appear, sometimes in the same sentence. Standardize to "
  "“Grok” and “Claude” in the body text.")

P("17. Author name. The byline and Author Contributions use “David Ims,” but Table 2 (Grok "
  "quote) says “P. David Imes.” As verbatim AI output it may stand; flagged for awareness.")

P("18. Repetition (§4.1). “This was demonstrated by Collura and Tarrant when they demonstrated "
  "…” — reword one verb.")

P("19. Reference dates. Table 5 lists Tjepkema-Cloostermans “2024”; reference [23] is dated "
  "2025. Reconcile.")

P("20. Author initial. Reference [2] has “Brubaker, B.” while reference [17] has "
  "“Brubaker, H.” — verify (same author?).")

P("21. Terminology (§3.2.2). “autistic spectrum disorder” → “autism spectrum "
  "disorder” (standard term; ASD already used).")

H("Outstanding typesetter queries (AQ1–AQ7)", 2)
BU("AQ1 / AQ2: add the missing closing quotation marks in Table 2; expand “SREMs” "
   "(slow rolling eye movements).")
BU("AQ3: expand “CNN” (convolutional neural network) at first mention.")
BU("AQ4: expand “FDR” (false discovery rate).")
BU("AQ5: expand “AUC” (area under the curve).")
BU("AQ6: addressed in Item 8 above.")
BU("AQ7: expand “CFR” (Code of Federal Regulations) at first mention.")

out = os.path.join(os.getcwd(), "AIA62026679_editor_corrections.docx")
build(B, out, title="Author Corrections to Proofs — AIA62026679")
print("wrote", out)
