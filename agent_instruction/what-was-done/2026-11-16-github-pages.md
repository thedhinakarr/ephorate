# GitHub push and Pages publication — 2026-11-16

The owner explicitly requested committing and pushing M1 to the personal public repository, then deploying the site on GitHub Pages.

- Pushed M1 commit `4a3c04c8de255da12b79f531e895481c1166e86a` and subsequent website work to `implementation/removal-check-m1` in `thedhinakarr/ephorate`. Verified the repository owner is the personal GitHub user. No merge into `main` was performed.
- Retained the supplied mono/console design. Added native disclosures for folded example code, named keyboard-scrollable regions, contrasting focus outlines and an informative no-JavaScript fallback. Source/plan links now point to the current implementation branch. Clarified that package publication is separate from website publication.
- Published only `index.html` and `.nojekyll` on `gh-pages`. GitHub enabled branch-source Pages when that branch was pushed; its settings were verified as root `/`, legacy build, HTTPS enforced and no custom domain.
- Verified the site at [thedhinakarr.github.io/ephorate](https://thedhinakarr.github.io/ephorate/). No domain registration, DNS change, PyPI release, external repository replay or M2 continuation was included.
- Investigated a CI preservation-test failure: background Git maintenance from fixture creation removed a lock file between snapshots. Disabled automatic maintenance and garbage collection in the fixture-only Git helper, matching the production boundary. Kept the byte-for-byte source-preservation assertion unchanged.

Future site updates must copy the reviewed `index.html` to the existing `gh-pages` branch and fast-forward it. Preserve `.nojekyll`, keep other repository files out of the site artifact, and verify the Pages build plus live content after pushing. The source branch does not automatically synchronize this content-only publication branch.

See [observed results](../what-was-the-result/2026-11-16-github-pages.md) for checks, CI outcomes and limitations.
