#!/usr/bin/env python3
"""Build the synthetic cardiac-inflammation MRI corpus and the private planted key for the gap/proposal task."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
PUB = HERE.parent / 'public' / 'inputs'

NOTE = ("SYNTHETIC CORPUS. Every record below is fictional and was written for this evaluation. The records do not describe real studies, "
        "real authors or real patients; all numbers are invented but chosen to be physiologically plausible. Cite records only by their IDs (M01..M35).")
R = []
def rec(id, title, year, design, population, pop, n, groups, B0, vendor, tech, techdet, ref, refcode, methods, numbers, success, abstract):
    R.append(dict(id=id, title=title, year=year, study_design=design, population=population, population_code=pop, n_total=n, groups=groups,
                  field_strength_T=B0, vendor=vendor, technique_codes=tech, technique_details=techdet, reference_standard=ref, reference_code=refcode,
                  methods_summary=methods, key_numbers=numbers, technical_success=success, abstract=abstract))

BXDEF = ('active myocardial inflammation on endomyocardial biopsy assessed by immunohistochemistry (leukocytes and CD3+ T lymphocytes per mm2); '
         'reference-positive = at least 14 leukocytes/mm2 including at least 7 CD3+ T lymphocytes/mm2')
OUT = 'prospective cardiac outcome during follow-up (cardiovascular death, heart-failure hospitalisation or sustained ventricular arrhythmia)'
T2D = 'T2-prepared bSSFP T2 mapping on three short-axis slices; global mid-wall ROIs excluding blood pool and epicardial fat'
MYOP = 'adults with suspected acute myocarditis undergoing endomyocardial biopsy'
ICIP = 'patients receiving immune checkpoint inhibitors with suspected myocarditis'

rec('M01', 'Repeatability of myocardial T2, native T1 and ECV mapping at 1.5 T in healthy volunteers', 2018, 'prospective repeatability study', 'healthy volunteers', 'HV', 24,
    'single group, two sessions 3-10 days apart', 1.5, 'Vendor A', ['T2', 'T1', 'ECV'], 'T2-prepared bSSFP T2 mapping; MOLLI 5(3)3 native and post-contrast T1; ECV with same-day haematocrit',
    'test-retest agreement', 'REPEAT', 'No strenuous exercise for 48 h before each scan; septal mid-wall ROIs excluding blood pool.',
    {'T2_ms_mean_sd': '50.8 +/- 2.4', 'T2_within_subject_SD_ms': 1.1, 'native_T1_within_subject_SD_ms': 16, 'ECV_within_subject_SD_percent': 1.0},
    {'T2': '24/24 (100%)', 'T1': '24/24 (100%)', 'ECV': '23/24 (96%)'},
    'Twenty-four volunteers were scanned twice at 1.5 T after 48 h without strenuous exercise. Myocardial T2 was 50.8 +/- 2.4 ms with a within-subject SD of 1.1 ms; within-subject SDs were 16 ms for native T1 and 1.0 percentage point for ECV.')
rec('M02', 'Myocardial T2 depends on field strength and mapping sequence', 2019, 'prospective method comparison', 'healthy volunteers', 'HV', 30,
    'single group, all protocols within one visit', 1.5, 'Vendor B', ['T2'], 'T2-prepared bSSFP at 1.5 T and at 3 T; gradient and spin echo (GraSE) T2 mapping at 1.5 T', 'agreement between T2 protocols', 'CONF',
    'Bland-Altman comparison of identical septal ROIs.', {'T2_3T_minus_1p5T_bSSFP_ms_mean': -5.6, 'GraSE_minus_bSSFP_1p5T_ms_mean': -4.1, 'limits_of_agreement_GraSE_minus_bSSFP_ms': '-7.0 to -1.2'},
    {'T2': '30/30 (100%)'},
    'Myocardial T2 at 3 T was on average 5.6 ms shorter than at 1.5 T, and GraSE gave values 4.1 ms shorter than T2-prepared bSSFP at 1.5 T (limits of agreement -7.0 to -1.2 ms) in 30 volunteers. T2 values from different field strengths or sequences are not interchangeable and should not be pooled.')
rec('M03', 'Myocardial T2 mapping detects biopsy-proven inflammation in suspected acute myocarditis', 2018, 'prospective cross-sectional, consecutive patients referred for endomyocardial biopsy',
    MYOP, 'MYO', 78, 'inflammation positive: n = 33; inflammation negative: n = 45', 1.5, 'Vendor A', ['T2'], T2D, BXDEF, 'BX',
    'MRI within 3 days before biopsy; no strenuous exercise for 48 h; readers blinded to histology; pathologist blinded to MRI.',
    {'T2_ms_inflamed_mean_sd': '58.9 +/- 3.6', 'T2_ms_noninflamed_mean_sd': '54.6 +/- 3.1', 'difference_ms_95CI': '4.3 (2.8 to 5.8)', 'p': '<0.001', 'AUC': 0.80},
    {'T2': '76/78 (97%)'},
    'In 78 consecutive adults with suspected acute myocarditis undergoing biopsy, myocardial T2 was higher with active inflammation than without (58.9 +/- 3.6 vs 54.6 +/- 3.1 ms; difference 4.3 ms, 95% CI 2.8 to 5.8; p < 0.001; AUC 0.80).')
rec('M04', 'Endurance exercise raises myocardial T2 in healthy volunteers', 2017, 'prospective within-subject (paired) study', 'healthy volunteers', 'HV', 32,
    'single group scanned after 72 h without exercise and 1 h after a 90-minute run', 1.5, 'Vendor A', ['T2'], 'T2-prepared bSSFP; septal ROIs', 'within-subject change after endurance exercise', 'CONF',
    'Paired scans on one day; identical slice positions.', {'T2_change_after_exercise_ms_95CI': '+2.1 (1.3 to 2.9)', 'p': '<0.001'}, {'T2': '32/32 (100%)'},
    'Myocardial T2 rose by 2.1 ms (95% CI 1.3 to 2.9; p < 0.001, paired) one hour after a 90-minute run compared with rest in 32 volunteers. Strenuous exercise should be avoided before T2 mapping.')
rec('M05', 'Late gadolinium enhancement predicts adverse events after acute myocarditis', 2020, 'prospective cohort, median 4-year follow-up', 'adults with acute myocarditis', 'MYO', 310, 'single cohort', 1.5, 'Vendor B',
    ['LGE'], 'LGE extent as % of LV mass (full-width half-maximum)', OUT, 'EVENT', 'Cox model adjusted for LV ejection fraction and age; 38 events.',
    {'hazard_ratio_per_5_percent_LGE_95CI': '1.6 (1.3 to 2.0)', 'p': '<0.001'}, {'LGE': '298/310 (96%)'},
    'In 310 adults with acute myocarditis followed for a median of 4 years, each 5% of LV mass with LGE was associated with a hazard ratio of 1.6 (95% CI 1.3 to 2.0) for cardiovascular death, heart-failure hospitalisation or sustained ventricular arrhythmia.')
rec('M06', 'Native T1 and biopsy-proven inflammation in suspected myocarditis', 2018, 'cross-sectional biopsy comparison', MYOP, 'MYO', 74,
    'inflammation positive: n = 31; inflammation negative: n = 43', 3.0, 'Vendor B', ['T1'], 'MOLLI 5(3)3; global mid-wall ROIs excluding blood pool; slice thickness 8 mm',
    BXDEF, 'BX', 'MRI within 3 days of biopsy; blinded readers; immunohistochemistry with leukocyte and CD3+ counts.',
    {'native_T1_ms_inflamed_vs_noninflamed': '1298 +/- 52 vs 1246 +/- 47', 'p': '<0.001'}, {'T1': '73/74 (99%)'},
    'In 74 adults with suspected myocarditis, native T1 at 3 T was higher with active inflammation (1298 vs 1246 ms; p < 0.001).')
rec('M07', 'Native T1 in recent-onset dilated cardiomyopathy compared with healthy volunteers', 2019, 'case-control', 'adults with recent-onset dilated cardiomyopathy and healthy volunteers', 'DCM', 80,
    'dilated cardiomyopathy n = 54; volunteers n = 26', 1.5, 'Vendor C', ['T1'], 'MOLLI 5(3)3; septal ROIs', 'difference from healthy volunteers', 'HVDIFF',
    'No biopsy in this study.', {'native_T1_ms_DCM_vs_HV': '1041 +/- 38 vs 989 +/- 27', 'p': '<0.001'}, {'T1': '53/54 patients (98%)'},
    'Native T1 was higher in 54 adults with recent-onset dilated cardiomyopathy than in 26 volunteers (1041 vs 989 ms; p < 0.001).')
rec('M08', 'Myocardial T2 and immunohistochemical inflammation: a multicentre biopsy study', 2020, 'prospective cross-sectional, consecutive biopsy referrals', MYOP, 'MYO', 64,
    'inflammation positive: n = 28; inflammation negative: n = 36', 1.5, 'Vendor C', ['T2'], T2D, BXDEF, 'BX',
    'MRI within 3 days before biopsy; no strenuous exercise for 48 h; blinded readers.',
    {'T2_ms_inflamed_mean_sd': '59.6 +/- 4.1', 'T2_ms_noninflamed_mean_sd': '55.2 +/- 3.4', 'difference_ms_95CI': '4.4 (2.5 to 6.3)', 'p': '<0.001'}, {'T2': '63/64 (98%)'},
    'In 64 adults with suspected acute myocarditis, myocardial T2 was 59.6 +/- 4.1 ms with active inflammation and 55.2 +/- 3.4 ms without (difference 4.4 ms, 95% CI 2.5 to 6.3; p < 0.001).')
rec('M09', 'Extracellular volume does not separate active from inactive inflammation', 2019, 'cross-sectional biopsy comparison', MYOP, 'MYO', 90,
    'inflammation positive: n = 37; inflammation negative: n = 53', 1.5, 'Vendor B', ['ECV'], 'MOLLI before and 15 min after contrast; same-day haematocrit; global ROIs', BXDEF, 'BX',
    'MRI within 3 days of biopsy; blinded readers.', {'ECV_percent_inflamed_vs_noninflamed': '30.1 +/- 3.8 vs 29.4 +/- 3.5', 'p': 0.38}, {'ECV': '87/90 (97%)'},
    'In 90 adults with suspected myocarditis, ECV did not differ by biopsy inflammation (30.1 vs 29.4%; p = 0.38).')
rec('M10', 'Native T1 does not reflect biopsy inflammation in suspected myocarditis', 2018, 'cross-sectional biopsy comparison', MYOP, 'MYO', 70,
    'inflammation positive: n = 29; inflammation negative: n = 41', 1.5, 'Vendor A', ['T1'], 'MOLLI 5(3)3; global mid-wall ROIs excluding blood pool; slice thickness 8 mm',
    BXDEF, 'BX', 'MRI 14 to 30 days after the diagnostic biopsy; blinded readers; immunohistochemistry with leukocyte and CD3+ counts.',
    {'native_T1_ms_inflamed_vs_noninflamed': '1012 +/- 41 vs 1003 +/- 39', 'p': 0.35}, {'T1': '69/70 (99%)'},
    'In 70 adults with suspected myocarditis, native T1 at 1.5 T did not differ between patients with and without active inflammation on biopsy (1012 vs 1003 ms; p = 0.35).')
rec('M11', 'Myocardial T2 and inflammatory cardiomyopathy in recent-onset dilated cardiomyopathy', 2021, 'prospective cross-sectional, consecutive biopsy referrals',
    'adults with recent-onset dilated cardiomyopathy undergoing endomyocardial biopsy', 'DCM', 72, 'inflammation positive: n = 21; inflammation negative: n = 51', 1.5, 'Vendor B', ['T2'], T2D, BXDEF, 'BX',
    'MRI within 3 days before biopsy; no strenuous exercise for 48 h; blinded readers; viral genome analysis reported separately.',
    {'T2_ms_inflamed_vs_noninflamed': '57.8 +/- 3.5 vs 54.1 +/- 3.0', 'difference_ms_95CI': '3.7 (2.0 to 5.4)', 'p': '<0.001'}, {'T2': '70/72 (97%)'},
    'In 72 adults with recent-onset dilated cardiomyopathy, myocardial T2 was higher with active inflammation on biopsy (57.8 vs 54.1 ms; difference 3.7 ms, 95% CI 2.0 to 5.4; p < 0.001).')
rec('M12', 'Shortened MOLLI native T1 in suspected myocarditis', 2020, 'cross-sectional biopsy comparison', MYOP, 'MYO', 37,
    'inflammation positive: n = 15; inflammation negative: n = 22', 1.5, 'Vendor C', ['T1'], 'ShMOLLI; global mid-wall ROIs excluding blood pool; slice thickness 6 mm',
    BXDEF, 'BX', 'MRI within 3 days of biopsy; blinded readers; immunohistochemistry with leukocyte and CD3+ counts.',
    {'native_T1_ms_inflamed_vs_noninflamed': '1032 +/- 36 vs 985 +/- 33', 'p': '<0.001'}, {'T1': '37/37 (100%)'},
    'In 37 adults with suspected myocarditis, native T1 at 1.5 T was higher with active inflammation (1032 vs 985 ms; p < 0.001).')
rec('M13', 'Feasibility and repeatability of myocardial T2 mapping in patients receiving immune checkpoint inhibitors', 2021, 'prospective technical study', ICIP, 'ICI', 80,
    'single cohort; test-retest subset n = 20', 1.5, 'Vendor A', ['T2'], T2D, 'technical success and test-retest repeatability', 'REPEAT',
    'No strenuous exercise for 48 h. No biopsy was obtained in this study.',
    {'analysable_T2_maps': '76/80 (95%)', 'non_evaluable_fraction': '4/80 = 5.0%', 'T2_ms_mean': 55.9, 'between_subject_SD_ms': 3.6, 'within_subject_SD_ms': 1.2},
    {'T2': '76/80 (95%)'},
    'T2 mapping was attempted in 80 patients receiving immune checkpoint inhibitors; 76 (95%) had analysable maps and 4 (5.0%) were non-evaluable. Mean myocardial T2 was 55.9 ms with a between-subject SD of 3.6 ms, and the within-subject SD in 20 repeated examinations was 1.2 ms.')
rec('M14', 'Myocardial T2 mapping and inflammation in a large endomyocardial biopsy cohort', 2022, 'prospective cross-sectional, consecutive biopsy referrals', MYOP, 'MYO', 96,
    'inflammation positive: n = 41; inflammation negative: n = 55', 1.5, 'Vendor B', ['T2'], T2D, BXDEF, 'BX',
    'MRI within 3 days before biopsy; no strenuous exercise for 48 h; blinded readers.',
    {'T2_ms_inflamed_mean_sd': '60.4 +/- 3.9', 'T2_ms_noninflamed_mean_sd': '55.0 +/- 3.2', 'difference_ms_95CI': '5.4 (3.9 to 6.9)', 'p': '<0.001'}, {'T2': '94/96 (98%)'},
    'In 96 consecutive adults with suspected acute myocarditis, myocardial T2 was 60.4 +/- 3.9 ms with active inflammation and 55.0 +/- 3.2 ms without (difference 5.4 ms, 95% CI 3.9 to 6.9; p < 0.001).')
rec('M15', 'T2-weighted edema ratio in dilated cardiomyopathy and healthy volunteers', 2020, 'case-control', 'adults with recent-onset dilated cardiomyopathy and healthy volunteers', 'DCM', 64,
    'dilated cardiomyopathy n = 42; volunteers n = 22', 1.5, 'Vendor C', ['EDR'], 'dark-blood T2-weighted STIR; myocardium-to-skeletal-muscle signal ratio', 'difference from healthy volunteers', 'HVDIFF',
    'No biopsy in this study.', {'edema_ratio_DCM_vs_HV': '2.01 +/- 0.31 vs 1.72 +/- 0.22', 'p': '<0.001'}, {'EDR': '61/64 (95%)'},
    'The T2-weighted edema ratio was higher in 42 adults with recent-onset dilated cardiomyopathy than in 22 volunteers (2.01 vs 1.72; p < 0.001).')
rec('M16', 'Native T1 at endomyocardial biopsy in suspected immune checkpoint inhibitor myocarditis', 2021, 'prospective cross-sectional, consecutive biopsies', ICIP, 'ICI', 88,
    'adequate biopsies n = 83 (inflammation positive: n = 30; inflammation negative: n = 53)', 1.5, 'Vendor A', ['T1'], 'MOLLI 5(3)3; global mid-wall ROIs excluding blood pool', BXDEF, 'BX',
    'MRI within 3 days before biopsy and before high-dose corticosteroids; biopsy adequacy required at least 4 samples with at least 2 mm2 of myocardium; blinded readers.',
    {'biopsy_inadequate': '5/88 (5.7%)', 'inflammation_positive_among_adequate_biopsies': '30/83 (36.1%)', 'native_T1_ms_inflamed_vs_noninflamed': '1068 +/- 45 vs 1017 +/- 40', 'p': '<0.001'},
    {'T1': '86/88 (98%)'},
    'Eighty-eight patients with suspected immune checkpoint inhibitor myocarditis had native T1 mapping before biopsy. Five biopsies (5.7%) were inadequate; among 83 adequate biopsies, 30 (36.1%) showed active inflammation, with higher native T1 than the others (1068 vs 1017 ms; p < 0.001).')
rec('M17', 'Native T1 mapping and myocardial inflammation: a negative biopsy study', 2020, 'cross-sectional biopsy comparison', MYOP, 'MYO', 82,
    'inflammation positive: n = 35; inflammation negative: n = 47', 3.0, 'Vendor B', ['T1'], 'ShMOLLI; global mid-wall ROIs excluding blood pool; slice thickness 8 mm',
    BXDEF, 'BX', 'MRI 14 to 30 days after the diagnostic biopsy; blinded readers; immunohistochemistry with leukocyte and CD3+ counts.',
    {'native_T1_ms_inflamed_vs_noninflamed': '1221 +/- 49 vs 1212 +/- 46', 'p': 0.40}, {'T1': '80/82 (98%)'},
    'In 82 adults with suspected myocarditis, native T1 at 3 T did not differ by biopsy inflammation (1221 vs 1212 ms; p = 0.40).')
rec('M18', 'Global longitudinal strain and biopsy inflammation', 2019, 'cross-sectional biopsy comparison', MYOP, 'MYO', 70,
    'inflammation positive: n = 30; inflammation negative: n = 40', 1.5, 'Vendor C', ['STRAIN'], 'feature-tracking global longitudinal strain from cine bSSFP', BXDEF, 'BX',
    'MRI within 3 days of biopsy; blinded readers.', {'GLS_percent_inflamed_vs_noninflamed': '-15.9 +/- 2.8 vs -16.4 +/- 2.6', 'p': 0.44}, {'STRAIN': '69/70 (99%)'},
    'In 70 adults with suspected myocarditis, global longitudinal strain did not differ by biopsy inflammation (-15.9 vs -16.4%; p = 0.44).')
rec('M19', 'Feature-tracking strain predicts events in cardiac sarcoidosis: a pilot study', 2019, 'prospective pilot cohort, 2-year follow-up', 'adults with cardiac sarcoidosis', 'SARC', 16,
    'patients with events n = 7; without events n = 9', 1.5, 'Vendor B', ['STRAIN'], 'feature-tracking global longitudinal strain', OUT, 'EVENT', 'Single-centre pilot; unadjusted comparison.',
    {'GLS_percent_events_vs_no_events': '-12.1 +/- 2.4 vs -15.6 +/- 2.2', 'p': 0.008, 'AUC': 0.87}, {'STRAIN': '16/16 (100%)'},
    'In 16 adults with cardiac sarcoidosis, baseline global longitudinal strain was less negative in the 7 with events than in the 9 without (-12.1 vs -15.6%; p = 0.008; AUC 0.87). Strain is a strong predictor of adverse events in cardiac sarcoidosis.')
rec('M20', 'LGE extent and outcomes in cardiac sarcoidosis', 2022, 'prospective cohort, median 3-year follow-up', 'adults with cardiac sarcoidosis', 'SARC', 164, 'single cohort', 1.5, 'Vendor A',
    ['LGE'], 'LGE extent as % of LV mass', OUT, 'EVENT', 'Cox model adjusted for LV ejection fraction; 33 events.',
    {'hazard_ratio_per_5_percent_LGE_95CI': '1.5 (1.2 to 1.8)', 'p': '<0.001'}, {'LGE': '157/164 (96%)'},
    'In 164 adults with cardiac sarcoidosis, each 5% of LV mass with LGE was associated with a hazard ratio of 1.5 (95% CI 1.2 to 1.8) for cardiovascular death, heart-failure hospitalisation or sustained ventricular arrhythmia.')
rec('M21', 'Diagnostic performance of T2 mapping for biopsy-proven active myocarditis', 2023, 'prospective cross-sectional, consecutive biopsy referrals', MYOP, 'MYO', 70,
    'inflammation positive: n = 30; inflammation negative: n = 40', 1.5, 'Vendor A', ['T2'], T2D, BXDEF, 'BX',
    'MRI within 3 days before biopsy; no strenuous exercise for 48 h; blinded readers.',
    {'T2_ms_inflamed_mean_sd': '59.1 +/- 3.7', 'T2_ms_noninflamed_mean_sd': '55.7 +/- 3.3', 'difference_ms_95CI': '3.4 (1.7 to 5.1)', 'p': '<0.001'}, {'T2': '68/70 (97%)'},
    'In 70 adults with suspected acute myocarditis, myocardial T2 was 59.1 +/- 3.7 ms with active inflammation and 55.7 +/- 3.3 ms without (difference 3.4 ms, 95% CI 1.7 to 5.1; p < 0.001).')
rec('M22', 'Myocardial T2 in patients receiving immune checkpoint inhibitors compared with healthy volunteers', 2022, 'case-control', 'patients receiving immune checkpoint inhibitors and healthy volunteers', 'ICI', 77,
    'ICI-treated patients n = 53; volunteers n = 24', 1.5, 'Vendor B', ['T2'], T2D, 'difference from healthy volunteers', 'HVDIFF',
    'No strenuous exercise for 48 h. No biopsy was performed.', {'T2_ms_ICI_vs_HV': '55.4 +/- 3.8 vs 51.2 +/- 2.6', 'p': '<0.001'}, {'T2': '49/53 patients (92%)'},
    'Myocardial T2 was higher in 53 patients receiving immune checkpoint inhibitors than in 24 volunteers (55.4 +/- 3.8 vs 51.2 +/- 2.6 ms; p < 0.001); T2 maps were analysable in 49/53 patients (92%).')
rec('M23', 'High-dose corticosteroids lower myocardial T2 within days in immune checkpoint inhibitor myocarditis', 2020, 'prospective within-subject study', ICIP, 'ICI', 34,
    'single group scanned before and 3 to 5 days after the start of high-dose methylprednisolone', 1.5, 'Vendor A', ['T2'], T2D, 'effect of corticosteroid treatment on the MRI measure', 'TREAT',
    'Myocarditis diagnosed clinically (troponin rise and ECG changes); no biopsies were taken.',
    {'T2_change_after_corticosteroids_ms_95CI': '-3.2 (-4.3 to -2.1)', 'p': '<0.001'}, {},
    'In 34 patients scanned before and 3 to 5 days after starting high-dose corticosteroids, myocardial T2 fell by 3.2 ms (95% CI 2.1 to 4.3). Treatment lowers T2 within days, independently of the inflammation present before treatment; MRI should precede treatment or treatment timing should be recorded.')
rec('M24', 'T2-weighted edema ratio at endomyocardial biopsy in suspected immune checkpoint inhibitor myocarditis', 2023, 'cross-sectional biopsy comparison, consecutive biopsies', ICIP, 'ICI', 95,
    'adequate biopsies n = 88', 1.5, 'Vendor C', ['EDR'], 'dark-blood T2-weighted STIR edema ratio', BXDEF, 'BX',
    'MRI within 3 days before biopsy and before high-dose corticosteroids; biopsy adequacy required at least 4 samples with at least 2 mm2 of myocardium; blinded readers.',
    {'biopsy_inadequate': '7/95 (7.4%)', 'inflammation_positive_among_adequate_biopsies': '29/88 (33.0%)', 'edema_ratio_inflamed_vs_noninflamed': '1.98 +/- 0.34 vs 1.92 +/- 0.31', 'p': 0.41},
    {'EDR': '93/95 (98%)'},
    'Ninety-five patients with suspected immune checkpoint inhibitor myocarditis had T2-weighted imaging before biopsy. Seven biopsies (7.4%) were inadequate; among 88 adequate biopsies, 29 (33.0%) showed active inflammation. The edema ratio did not differ by inflammation (1.98 vs 1.92; p = 0.41).')
rec('M25', 'Global longitudinal strain in cardiac sarcoidosis with preserved ejection fraction and healthy volunteers', 2018, 'case-control', 'adults with cardiac sarcoidosis and healthy volunteers', 'SARC', 60,
    'cardiac sarcoidosis n = 40; volunteers n = 20', 1.5, 'Vendor C', ['STRAIN'], 'feature-tracking global longitudinal strain', 'difference from healthy volunteers', 'HVDIFF',
    'Patients with preserved ejection fraction only.', {'GLS_percent_SARC_vs_HV': '-18.6 +/- 2.3 vs -19.2 +/- 2.0', 'p': 0.31}, {'STRAIN': '60/60 (100%)'},
    'Global longitudinal strain did not differ between 40 adults with cardiac sarcoidosis and preserved ejection fraction and 20 volunteers (-18.6 vs -19.2%; p = 0.31).')
rec('M26', 'Extracellular volume in patients receiving immune checkpoint inhibitors compared with healthy volunteers', 2024, 'case-control', 'patients receiving immune checkpoint inhibitors and healthy volunteers', 'ICI', 74,
    'ICI-treated patients n = 50; volunteers n = 24', 1.5, 'Vendor B', ['ECV'], 'MOLLI before and after contrast; same-day haematocrit', 'difference from healthy volunteers', 'HVDIFF',
    'The study was designed because record M33 reported that ECV tracks inflammatory cell density on biopsy closely; no biopsy.',
    {'ECV_percent_ICI_vs_HV': '28.7 +/- 3.4 vs 25.9 +/- 2.6', 'p': 0.001}, {'ECV': '68/74 (92%)'},
    'Motivated by the close correlation with biopsy inflammation reported in record M33, we compared ECV in 50 patients receiving immune checkpoint inhibitors and 24 volunteers; ECV was higher in the patients (28.7 vs 25.9%; p = 0.001).')
rec('M27', 'Native T1 and inflammation at 3 T', 2022, 'cross-sectional biopsy comparison', MYOP, 'MYO', 88,
    'inflammation positive: n = 39; inflammation negative: n = 49', 3.0, 'Vendor A', ['T1'], 'MOLLI 5(3)3; global mid-wall ROIs excluding blood pool; slice thickness 8 mm',
    BXDEF, 'BX', 'MRI within 3 days of biopsy; blinded readers; immunohistochemistry with leukocyte and CD3+ counts.',
    {'native_T1_ms_inflamed_vs_noninflamed': '1302 +/- 50 vs 1249 +/- 44', 'p': '<0.001'}, {'T1': '86/88 (98%)'},
    'In 88 adults with suspected myocarditis, native T1 at 3 T was higher with active inflammation (1302 vs 1249 ms; p < 0.001).')
rec('M28', 'Position statement on strain imaging in cardiac sarcoidosis', 2022, 'expert position statement (no new data)', 'adults with cardiac sarcoidosis', 'SARC', 0, 'panel of 11 experts', None, None,
    ['STRAIN'], 'feature-tracking global longitudinal strain', 'none (position statement)', 'NONE', 'Consensus meeting; no systematic review; no new data.', {}, {},
    'The panel stated that global longitudinal strain reliably predicts adverse events in cardiac sarcoidosis (record M19) and recommended its use to select patients for implantable defibrillators.')
rec('M29', 'Edema ratio in patients receiving immune checkpoint inhibitors and healthy volunteers', 2021, 'case-control', 'patients receiving immune checkpoint inhibitors and healthy volunteers', 'ICI', 62,
    'ICI-treated patients n = 42; volunteers n = 20', 3.0, 'Vendor B', ['EDR'], 'dark-blood T2-weighted STIR edema ratio', 'difference from healthy volunteers', 'HVDIFF',
    'Patients scanned 2-6 months after starting treatment; no biopsy.', {'edema_ratio_ICI_vs_HV': '1.96 +/- 0.29 vs 1.74 +/- 0.21', 'p': 0.003}, {'EDR': '41/42 patients (98%)'},
    'The T2-weighted edema ratio was higher in 42 patients receiving immune checkpoint inhibitors than in 20 volunteers (1.96 vs 1.74; p = 0.003).')
rec('M30', 'Native T1 and biopsy inflammation: a second negative study', 2023, 'cross-sectional biopsy comparison', MYOP, 'MYO', 66,
    'inflammation positive: n = 27; inflammation negative: n = 39', 3.0, 'Vendor C', ['T1'], 'MOLLI 5(3)3; global mid-wall ROIs excluding blood pool; slice thickness 6 mm',
    BXDEF, 'BX', 'MRI 14 to 30 days after the diagnostic biopsy; blinded readers; immunohistochemistry with leukocyte and CD3+ counts.',
    {'native_T1_ms_inflamed_vs_noninflamed': '1218 +/- 47 vs 1207 +/- 45', 'p': 0.35}, {'T1': '65/66 (98%)'},
    'In 66 adults with suspected myocarditis, native T1 at 3 T did not differ by biopsy inflammation (1218 vs 1207 ms; p = 0.35).')
rec('M31', 'Late gadolinium enhancement in recent-onset dilated cardiomyopathy and healthy volunteers', 2022, 'case-control', 'adults with recent-onset dilated cardiomyopathy and healthy volunteers', 'DCM', 58,
    'dilated cardiomyopathy n = 38; volunteers n = 20', 1.5, 'Vendor A', ['LGE'], 'LGE presence and extent', 'difference from healthy volunteers', 'HVDIFF', 'No biopsy.',
    {'LGE_present_DCM_vs_HV': '16/38 vs 0/20', 'p': '<0.001'}, {'LGE': '37/38 patients (97%)'},
    'Mid-wall LGE was present in 16 of 38 adults with recent-onset dilated cardiomyopathy and in none of 20 volunteers (p < 0.001).')
rec('M32', 'Protocol: strain-guided defibrillator implantation in cardiac sarcoidosis, a randomised trial', 2023, 'trial protocol (no results)', 'adults with cardiac sarcoidosis', 'SARC', 220,
    'planned: strain-guided n = 110; standard care n = 110', 1.5, 'Vendor B', ['STRAIN'], 'feature-tracking global longitudinal strain', 'none (protocol)', 'NONE',
    'Planned sample size based on the strain difference reported in record M19.', {'planned_n': 220}, {},
    'This protocol describes a planned trial in which global longitudinal strain selects patients for defibrillator implantation, motivated by the predictive accuracy reported in record M19.')
rec('M33', 'ECV tracks inflammatory cell density in immune checkpoint inhibitor myocarditis: a pilot study', 2023, 'pilot cross-sectional biopsy correlation (no group comparison)', ICIP, 'ICI', 22,
    'single group; correlation analysis', 1.5, 'Vendor B', ['ECV'], 'MOLLI before and after contrast; same-day haematocrit', BXDEF, 'BX',
    'Single reader; timing of corticosteroids and blinding not reported.', {'Spearman_rho_ECV_vs_leukocytes_per_mm2': 0.81, 'p': '<0.001'}, {'ECV': '22/22 (100%)'},
    'In 22 patients with suspected immune checkpoint inhibitor myocarditis, ECV correlated closely with leukocyte density on biopsy (rho 0.81; p < 0.001). ECV could replace endomyocardial biopsy.')
rec('M34', 'Technical failure of breath-hold myocardial mapping in routine practice', 2020, 'retrospective technical audit', 'adults with suspected acute myocarditis referred for cardiac MRI', 'MYO', 410,
    'single cohort', 1.5, 'Vendor A', ['T1', 'T2'], 'breath-hold MOLLI 5(3)3 and breath-hold T2-prepared bSSFP', 'technical success', 'REPEAT',
    'Failure defined as visible respiratory misregistration or failed fitting in the myocardium.',
    {'T1_technical_success': '377/410 (92%)', 'T2_technical_success': '381/410 (93%)', 'failure_risk_factors': 'inability to hold the breath; respiratory drift between source images; arrhythmia'},
    {'T1': '377/410 (92%)', 'T2': '381/410 (93%)'},
    'Breath-hold myocardial mapping succeeded for native T1 in 377 of 410 adults (92%) and for T2 in 381 (93%); failures were caused by respiratory misregistration in patients unable to hold their breath and by arrhythmia.')
rec('M35', 'Native T1 and T2 normalise within weeks after acute myocarditis: a serial MRI study', 2021, 'prospective serial imaging study', 'adults with biopsy-proven acute myocarditis', 'MYO', 34,
    'single group scanned 1-3, 14 and 28 days after biopsy', 1.5, 'Vendor A', ['T1', 'T2'], 'MOLLI 5(3)3 and T2-prepared bSSFP; global mid-wall ROIs excluding blood pool', 'time course of the MRI measures after biopsy', 'CONF',
    'Serial scans with identical slice positions.',
    {'native_T1_change_day3_to_day28_ms': -48, 'T2_change_day3_to_day28_ms': -3.9, 'initial_T1_excess_remaining_at_day14_percent': 38},
    {'T1': '34/34 (100%)', 'T2': '34/34 (100%)'},
    'In 34 adults with biopsy-proven acute myocarditis, native T1 fell by 48 ms and T2 by 3.9 ms between days 1-3 and day 28 after biopsy; only 38% of the initial T1 excess remained at day 14. MRI performed two or more weeks after the biopsy no longer reflects the inflammation present at biopsy.')

TESTS = {
 'M01': [('T2','HV','REPEAT','feas',1), ('T1','HV','REPEAT','feas',1), ('ECV','HV','REPEAT','feas',1)], 'M02': [('T2','HV','CONF','pos',1)],
 'M03': [('T2','MYO','BX','pos',1)], 'M04': [('T2','HV','CONF','pos',1)], 'M05': [('LGE','MYO','EVENT','pos',1)], 'M06': [('T1','MYO','BX','pos',1)],
 'M07': [('T1','DCM','HVDIFF','pos',1)], 'M08': [('T2','MYO','BX','pos',1)], 'M09': [('ECV','MYO','BX','null',1)], 'M10': [('T1','MYO','BX','null',1)],
 'M11': [('T2','DCM','BX','pos',1)], 'M12': [('T1','MYO','BX','pos',1)], 'M13': [('T2','ICI','REPEAT','feas',1)], 'M14': [('T2','MYO','BX','pos',1)],
 'M15': [('EDR','DCM','HVDIFF','pos',1)], 'M16': [('T1','ICI','BX','pos',1)], 'M17': [('T1','MYO','BX','null',1)], 'M18': [('STRAIN','MYO','BX','null',1)],
 'M19': [('STRAIN','SARC','EVENT','pos',0)], 'M20': [('LGE','SARC','EVENT','pos',1)], 'M21': [('T2','MYO','BX','pos',1)], 'M22': [('T2','ICI','HVDIFF','pos',1)],
 'M23': [('T2','ICI','TREAT','pos',1)], 'M24': [('EDR','ICI','BX','null',1)], 'M25': [('STRAIN','SARC','HVDIFF','null',1)], 'M26': [('ECV','ICI','HVDIFF','pos',1)],
 'M27': [('T1','MYO','BX','pos',1)], 'M28': [('STRAIN','SARC','NONE','none',1)], 'M29': [('EDR','ICI','HVDIFF','pos',1)], 'M30': [('T1','MYO','BX','null',1)],
 'M31': [('LGE','DCM','HVDIFF','pos',1)], 'M32': [('STRAIN','SARC','NONE','none',1)], 'M33': [('ECV','ICI','BX','pos',0)], 'M34': [('T1','MYO','REPEAT','feas',1), ('T2','MYO','REPEAT','feas',1)],
 'M35': [('T1','MYO','CONF','pos',1), ('T2','MYO','CONF','pos',1)],
}
SUCCESS = {}
for r in R:
    for t, s in r['technical_success'].items():
        frac = int(s.split('(')[1].split('%')[0]) / 100
        SUCCESS[(t, r['population_code'])] = max(SUCCESS.get((t, r['population_code']), 0), frac)

def enumerate_gaps():
    out = []
    for t in ['T2', 'T1', 'ECV', 'LGE', 'STRAIN', 'EDR']:
        for ref in ['BX', 'EVENT']:
            pos = {p for ts in TESTS.values() for (tt, p, rr, res, ad) in ts if tt == t and rr == ref and res == 'pos' and ad}
            contradicted = any(p in pos and any(tt == t and pp == p and rr == ref and res == 'null' and ad for ts in TESTS.values() for (tt, pp, rr, res, ad) in ts) for p in pos)
            for p in ['MYO', 'DCM', 'ICI', 'SARC']:
                examined = any(tt == t and pp == p and rr == ref for ts in TESTS.values() for (tt, pp, rr, res, ad) in ts)
                g3 = bool(pos - {p}) and not contradicted
                g4 = SUCCESS.get((t, p), 0) >= 0.85
                g5 = any(pp == p and rr == ref for ts in TESTS.values() for (tt, pp, rr, res, ad) in ts)
                if not examined and g3 and g4 and g5:
                    out.append((t, p, ref))
    return out

if __name__ == '__main__':
    gaps = enumerate_gaps()
    assert gaps == [('T2', 'ICI', 'BX')], gaps
    assert [r['id'] for r in R] == ['M%02d' % i for i in range(1, 36)]
    assert set(TESTS) == {r['id'] for r in R}
    for r in R:
        assert set(r['technique_codes']) >= {x[0] for x in TESTS[r['id']]}, r['id']
    (PUB / 'corpus.json').write_text(json.dumps({'note': NOTE, 'licence': 'Synthetic content written for this evaluation; free to use for the evaluation.', 'records': R}, indent=1) + '\n')
    lines = ['# Synthetic cardiac MRI study corpus (myocardial inflammation)', '', NOTE, '']
    for r in R:
        lines += [f"## {r['id']} - {r['title']} ({r['year']})", '', f"- Design: {r['study_design']}",
                  f"- Population: {r['population']} (code {r['population_code']}); n = {r['n_total']}; groups: {r['groups']}",
                  f"- Field strength: {r['field_strength_T']} T; platform: {r['vendor']}",
                  f"- Technique codes: {', '.join(r['technique_codes'])}; details: {r['technique_details']}",
                  f"- Reference standard: {r['reference_standard']} (code {r['reference_code']})", f"- Methods summary: {r['methods_summary']}",
                  '- Key numbers: ' + '; '.join(f'{k} = {v}' for k, v in r['key_numbers'].items()),
                  '- Technical success: ' + ('; '.join(f'{k}: {v}' for k, v in r['technical_success'].items()) or 'not applicable'), '', f"Abstract: {r['abstract']}", '']
    (PUB / 'corpus.md').write_text('\n'.join(lines))
    BXREC = ['M03', 'M06', 'M08', 'M09', 'M10', 'M11', 'M12', 'M14', 'M16', 'M17', 'M18', 'M21', 'M24', 'M27', 'M30', 'M35']
    ROIREC = ['M01', 'M03', 'M06', 'M08', 'M10', 'M11', 'M12', 'M13', 'M14', 'M16', 'M17', 'M21', 'M22', 'M27', 'M30', 'M35']
    # recruitment inputs: smaller-group fraction and non-evaluable fraction in the target population
    f16, f24 = 30 / 83, 29 / 88; fpool = (30 + 29) / (83 + 88)
    m13, m22 = 4 / 80, 4 / 53; r16, r24 = 5 / 88, 7 / 95
    pairs = [1 - (1 - a) * (1 - b) for a in (m13, m22, (4 + 4) / (80 + 53)) for b in (r16, r24, (5 + 7) / (88 + 95))] + [a + b for a in (m13, m22) for b in (r16, r24)]
    key = {
     'id_regex': r'\bM\d{2,3}\b',
     'record_ids': [r['id'] for r in R],
     'tests': {k: [list(x) for x in v] for k, v in TESTS.items()},
     'replicated': {'technique': 'T2', 'population': 'MYO', 'reference': 'BX', 'ids': ['M03', 'M08', 'M14', 'M21']},
     'contradiction': {'technique': 'T1', 'population': 'MYO', 'reference': 'BX', 'sig_ids': ['M06', 'M12', 'M27'], 'null_ids': ['M10', 'M17', 'M30'],
                       'tolerated_extra_ids': ['M16', 'M35'], 'factor': 'mri_to_biopsy_interval'},
     'underpowered': {'ids': ['M19', 'M33'], 'dependents': {'M19': ['M28', 'M32'], 'M33': ['M26']}},
     'gap': {'technique': 'T2', 'population': 'ICI', 'reference': 'BX', 'G3_ids': ['M03', 'M08', 'M14', 'M21', 'M11'], 'G4_ids': ['M13', 'M22'], 'G5_ids': ['M16', 'M24'],
             'allowed_support': ['M01', 'M02', 'M03', 'M04', 'M08', 'M11', 'M13', 'M14', 'M16', 'M21', 'M22', 'M23', 'M24', 'M34', 'M35'], 'forbidden_support': ['M19', 'M33'],
             'direction': 'higher', 'units': ['ms'], 'threshold_token': '14'},
     'design': {'type': ['prospective_cross_sectional'], 'unit_of_analysis': ['participant'], 'recruitment': ['consecutive']},
     'sample_size': {'alpha': 0.05, 'power': 0.9, 'sided': 2, 'range_tol': 0.1,
                     'delta_range': [3.4, 5.4], 'delta_sources': ['M03', 'M08', 'M14', 'M21', 'M11'],
                     'sd_range': [3.0, 4.1], 'sd_sources': ['M03', 'M08', 'M14', 'M21', 'M11', 'M13', 'M22'],
                     'frac_range': [round(min(f16, f24, fpool) - 0.005, 3), round(max(f16, f24, fpool) + 0.005, 3)], 'frac_sources': ['M16', 'M24'],
                     'nonev_range': [round(min(pairs) - 0.004, 3), round(max(pairs) + 0.005, 3)], 'nonev_sources_mri': ['M13', 'M22'], 'nonev_sources_ref': ['M16', 'M24']},
     'controls': {'required': {'blinded_image_analysis': [], 'exercise_abstinence_before_mri': ['M04'], 'corticosteroid_timing_control': ['M23'], 'fixed_field_strength_and_sequence': ['M02']},
                  'support_map': {'exercise_abstinence_before_mri': ['M04', 'M01', 'M03', 'M08', 'M11', 'M13', 'M14', 'M21', 'M22'], 'corticosteroid_timing_control': ['M23', 'M16', 'M24'],
                                  'fixed_field_strength_and_sequence': ['M02', 'M01', 'M13', 'M22'], 'mri_close_in_time_to_reference': BXREC,
                                  'blood_pool_excluded_roi_placement': ROIREC,
                                  'free_breathing_or_motion_corrected_acquisition': ['M34'], 'repeat_mri_subset': ['M01', 'M13']}},
     'md_max_words': 1500,
    }
    (HERE / 'key.json').write_text(json.dumps(key, indent=1) + '\n')
    print('records', len(R), 'gap', gaps, key['sample_size']['frac_range'], key['sample_size']['nonev_range'])
