# Citations for author check

Every entry below is a real, locatable work. **Provenance of the verification is
stated per entry** — either independent web verification performed for Paper 6
and recorded in `paper6/Paper6_BibVerification_Report.md` (2026-05-24), or
re-verified today. Nothing here is reconstructed from memory without a stated
check. Where a claim in §2 needs support I could not verify, it is listed in the
final section as an open gap rather than given a citation.

## A. Resolving the 14 `[REF:*]` placeholders

| Placeholder | Work | Verification |
|---|---|---|
| `REF:RCAEval` | Pham, L., Zhang, H., Ha, H., Salim, F., Zhang, X. (2025). RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data. *WWW Companion '25*, 777–780. DOI 10.1145/3701716.3715290 | **re-verified 2026-08-22** (ACM DL + dblp + arXiv:2412.17015); author order and DOI confirmed |
| `REF:MonitorRank` | Kim, M., Sumbaly, R., Shah, S. (2013). Root cause detection in a service-oriented architecture. *SIGMETRICS '13*; ACM SIGMETRICS Perf. Eval. Rev. 41(1), 93–104. DOI 10.1145/2465529.2465753 | Paper 6 report, clean |
| `REF:MicroRCA` | Wu, L., Tordsson, J., Elmroth, E., Kao, O. (2020). MicroRCA: Root cause localization of performance issues in microservices. *NOMS 2020*, 1–9. DOI 10.1109/NOMS47738.2020.9110353 | Paper 6 report, spot-checked ✅ |
| `REF:CausalRCA` | Xin, R., Chen, P., Zhao, Z. (2022). CausalRCA: Causal inference based precise fine-grained root cause localization for microservice applications. arXiv:2209.02500 [cs.SE] | Paper 6 report |
| `REF:BARO` | Pham, L., Ha, H., Zhang, H. (2024). BARO: Robust root cause analysis for microservices via multivariate Bayesian online change point detection. *PACMSE* 1(FSE), art. 98, 2214–2237. DOI 10.1145/3660805 | Paper 6 report, spot-checked ✅ |
| `REF:DejaVu` | Li, Z., Zhao, N., Li, M., Lu, X., Wang, L., Chang, D., Nie, X., Cao, L., Zhang, W., Sui, K., Wang, Y., Du, X., Duan, G., Pei, D. (2022). Actionable and interpretable fault localization for recurring failures in online service systems. *ESEC/FSE '22*, 14–25. DOI 10.1145/3540250.3549092 | Paper 6 report |
| `REF:yRCA` | Soldani, J., Forti, S., Brogi, A. (2023). yRCA: An explainable failure root cause analyser. *Science of Computer Programming* 230, art. 102997. DOI 10.1016/j.scico.2023.102997 | Paper 6 report, spot-checked ✅ (co-author name previously corrected) |
| `REF:Mamdani` | Mamdani, E. H., Assilian, S. (1975). An experiment in linguistic synthesis with a fuzzy logic controller. *Int. J. Man-Machine Studies* 7(1), 1–13. DOI 10.1016/S0020-7373(75)80002-2 | Paper 6 report |
| `REF:Pearl1988` | Pearl, J. (1988). *Probabilistic Reasoning in Intelligent Systems: Networks of Plausible Inference*. Morgan Kaufmann. | Paper 6 report |
| `REF:NoyMcGuinness` | Noy, N. F., McGuinness, D. L. (2001). Ontology development 101: A guide to creating your first ontology. Stanford KSL Technical Report KSL-01-05. | Paper 6 report |
| `REF:failure-pattern-surveys` | Liu, B. (2019). Ontology-based fault diagnosis: A decade in review. *ICCMS '19*. DOI 10.1145/3307363.3307381 — **and** Notaro, P., Cardoso, J., Gerndt, M. (2020). A systematic mapping study in AIOps. *ICSOC 2020 Workshops*, LNCS 12632, 110–123. DOI 10.1007/978-3-030-76352-7_15 | Paper 6 report |
| `REF:Tbilisi` | Gardashova, L., Mirzazada, A., Kosov, P. A Semantic Approach to Explanation Generation for Fuzzy Diagnostic Analysis of Microservices. Springer LNNS. | **AUTHOR-ONLY** — title and authors read from the PDF at `~/research/papers/Paper_Tbilisi_revised_final.pdf`; **volume, page range, year and DOI are not in my possession**. Author must supply. |
| `REF:repo` | Software artifact: `https://github.com/alikmirza/foda-fuzzy-ontology-diagnostics`, tag `v1.0-method-paper` | **AUTHOR-ONLY** — Zenodo DOI not yet minted |
| `REF:AICT` | **not cited** (Option C). §1 carries a disclosure sentence instead. Upgrade to a proceedings citation only if accepted before submission. | status unchecked — author action |

## B. New citations for the §2 expansion

All from Paper 6's verified list unless marked otherwise. Grouped by the coverage
the brief requires.

### LLM-based RCA — the largest gap

| Work | Cited for |
|---|---|
| Zhang, L., Jia, T., Wang, K., Hong, W., Duan, C., He, M., Li, Y. (2025). Adaptive Root Cause Localization for Microservice Systems with Multi-Agent Recursion-of-Thought (RCLAgent). arXiv:2508.20370 [cs.SE] — **re-verified 2026-08-22**, authors and method name confirmed | the recursion-of-thought agent line; RCA framed as multi-step LLM reasoning rather than ranking |
| Tang, P., Tang, S., Pu, H., Miao, Z., Wang, Z. (2025). MicroRCA-Agent: Microservice root cause analysis method based on large language model agents. arXiv:2509.15635 [cs.SE] | multimodal LLM agents over metrics, logs and traces |
| Naakka, A., Wang, R., Erlenhov, L., Stirbu, V., Mikkonen, T. (2026). Multi-agent systems for root cause analysis in microservices. arXiv:2605.03505 [cs.SE] | the multi-agent framing, and its use of self-assessed reflection criteria as internal reward |
| Zhang, W., Guo, H., Yang, J., Tian, Z., Zhang, Y., Yan, C., Li, Z., Li, T., Shi, X., Zheng, L., Zhang, B. (2024). mABC: Multi-agent blockchain-inspired collaboration for root cause analysis in micro-services architecture. *Findings of EMNLP 2024*, 4017–4033 | agent-voting approaches; published venue confirmed in Paper 6 report |
| Li, J., Jia, T., Wang, R., Mei, B., He, M., Duan, C., Pei, J., Liu, J., Cai, M., Li, Y. (2025). Flow-of-Action: SOP-enhanced LLM-based multi-agent system for root cause analysis. *WWW Companion '25*, 422–431 | aligning agent reasoning with SRE standard operating procedures |
| Zhang, L., Jia, T., Zhai, Y., Pan, L., Duan, C., He, M., Xiao, P., Li, Y. (2026). Hypothesize-then-verify: Speculative root cause analysis for microservices with pathwise parallelism (SpecRCA). *ICSE-NIER '26*; arXiv:2601.02736 | the hypothesise-then-verify pattern, closest in spirit to our predict-then-verify methodology |

### Microservice RCA beyond the six evaluated baselines

| Work | Cited for |
|---|---|
| Ma, M., Xu, J., Wang, Y., Chen, P., Zhang, Z., Wang, P. (2020). AutoMAP: Diagnose your microservice-based web applications automatically. *WWW '20*, 246–258. DOI 10.1145/3366423.3380111 | propagation with self-loop and backward edges (author list corrected in Paper 6 round) |
| Ma, M., Lin, W., Pan, D., Wang, P. (2019). MS-Rank: Multi-metric and self-adaptive root cause diagnosis. *ICWS 2019*, 60–67. DOI 10.1109/ICWS.2019.00022 | typed forward/selfward/backward propagation |
| Li, M., Li, Z., Yin, K., Nie, X., Zhang, W., Sui, K., Pei, D. (2022). Causal inference-based root cause analysis for online service systems with intervention recognition (CIRCA). *KDD '22*, 3230–3240. DOI 10.1145/3534678.3539041 | causal Bayesian networks for RCA |
| Ding, R. et al. (2023). TraceDiag: Adaptive, interpretable, and efficient root cause analysis on large-scale microservice systems. *ESEC/FSE '23*, 1762–1773. DOI 10.1145/3611643.3613864 | learned interpretable graph-pruning policy |
| Yu, G., Chen, P., Li, Y., Chen, H., Li, X., Zheng, Z. (2023). Nezha: Interpretable fine-grained root causes analysis for microservices on multi-modal observability data. *ESEC/FSE '23*, 553–565. DOI 10.1145/3611643.3616249 | interpretability claims on multi-modal data |
| Wang, T., Qi, G., Wu, T. (2024). KGroot: A knowledge graph-enhanced method for root cause analysis. *Expert Systems with Applications* 255, art. 124679. DOI 10.1016/j.eswa.2024.124679 | knowledge graphs as features rather than as shared vocabulary — directly supports the empty-middle argument |

### Ontology-based fault diagnosis outside microservices

| Work | Cited for |
|---|---|
| Liu, B. (2019). Ontology-based fault diagnosis: A decade in review. *ICCMS '19*. DOI 10.1145/3307363.3307381 | the industrial-diagnosis lineage and why its assumptions do not transfer directly |
| Chari, S., Seneviratne, O., Gruen, D. M., Foreman, M. A., Das, A. K., McGuinness, D. L. (2020). Explanation Ontology: A Model of Explanations for User-Centered AI. *ISWC 2020*, LNCS 12506, 228–243. DOI 10.1007/978-3-030-62466-8_15 | an upper-level ontology *of explanations*, complementary to our domain ontology (title corrected in the Paper 6 verification round) |
| Shetty, M., Bansal, C., Kumar, S., Rao, N., Nagappan, N. (2022). SoftNER: Mining knowledge graphs from cloud incidents. *EMSE* 27(5), art. 93. DOI 10.1007/s10664-022-10159-w | knowledge extraction from incident reports (author list corrected in Paper 6 round) |

### Fuzzy diagnosis beyond the original Mamdani reference

| Work | Cited for |
|---|---|
| Zadeh, L. A. (1965). Fuzzy sets. *Information and Control* 8(3), 338–353. DOI 10.1016/S0019-9958(65)90241-X | graded membership as the semantic basis for H(s) |
| Gardashova, L. A. (2023). *Fuzzy Logic and Its Applications*. ASOIU Publishing House, Baku. | applications-oriented treatment; **self-citation — flag for the author to decide whether to keep** |

### RCA and explanation evaluation beyond RCAEval

| Work | Cited for |
|---|---|
| Doshi-Velez, F., Kim, B. (2017). Towards a rigorous science of interpretable machine learning. arXiv:1702.08608 [stat.ML] | the functionally-grounded evaluation category our metrics occupy |
| Lipton, Z. C. (2018). The mythos of model interpretability. *CACM* 61(10), 36–43. DOI 10.1145/3233231 | that "interpretability" conflates distinct desiderata — motivates measuring four separate dimensions |
| Jacovi, A., Goldberg, Y. (2020). Towards faithfully interpretable NLP systems: How should we define and evaluate faithfulness? *ACL 2020*, 4198–4205. DOI 10.18653/v1/2020.acl-main.386 | plausibility vs faithfulness; our metrics are behavioural, not faithfulness certificates |

## C. Claims that need a citation and have none verified

Leave these sentences unsupported for the author to fill. **Do not invent a
reference for any of them.**

1. **§2.3's "we are not aware of prior work in microservice RCA that both grounds
   explanations in a shared ontology and reports where that grounding fails to
   help."** This is a negative claim about the literature. The survey above is
   the strongest support I can offer, but a negative claim of this form should
   either be softened to what the survey actually establishes or supported by a
   systematic search whose protocol is stated. **Recommend softening.**
2. **§4.2's SLO-calibrated thresholds** (marker 8) — the CRITICAL latency knee at
   400–600 ms and the HIGH error-rate onset at 10–15 % are described as
   reflecting common service-level objectives. No source for those figures is in
   the repository. **AUTHOR-ONLY: supply a citation or drop the SLO claim and
   present the thresholds as chosen by the authors.**
3. **§3.2's competency questions** (marker 2) — whether CQ1–CQ5 were the
   design-time questions is author knowledge, not a citable claim.

## D. Verification method, stated plainly

Two entries were re-verified today by web search against primary sources (ACM DL,
dblp, arXiv). The remainder are carried from an independent verification
performed for Paper 6 on 2026-05-24, which the report itself documents as having
caught two substantive errors in entries previously marked clean — so it is
evidence of a real process, not a rubber stamp. **Before submission every entry
should still be opened once by a human**, because the failure mode that matters
here is not a wrong page range but a work that does not exist, and only a human
opening the DOI can fully close that.
