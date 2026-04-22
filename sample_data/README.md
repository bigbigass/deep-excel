# Sample Scenarios

Use these files from `sample_data/` to exercise different report paths.

| File | Scenario | Expected template | What to look for |
| --- | --- | --- | --- |
| `normal_batch.csv` | Stable process, high capability, no failures | `template_c_showcase` | AI summary should emphasize low risk and strong Cpk. |
| `shifted_mean_batch.csv` | All points pass, but the mean drifts toward the upper limit | `template_b_detailed` | AI summary should mention “all pass but capability is weak”. |
| `high_variation_batch.csv` | All points pass, but spread is too wide | `template_b_detailed` | AI summary should focus on high variation and future risk. |
| `out_of_spec_batch.csv` | Clear out-of-spec points and low pass rate | `template_a_overview` | AI summary should highlight urgent quality risk and corrective actions. |

Recommended quick check:

1. Upload a CSV from this folder.
2. Wait for analysis to finish.
3. Confirm `template_id` on the job payload or report page.
4. Compare the narrative blocks in the rendered report: `summary`, `risk`, and `actions`.
