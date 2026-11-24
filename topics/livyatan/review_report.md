# Review report: Livyatan: The Megatooth Whale

Generated 2026-11-24T19:16:57+00:00

## Summary

| Item | Count |
|---|---|
| Shots | 26 |
| Images ready | 0 / 26 |
| Hero shots (motion clips) | 12 |
| Motion clips ready | 0 / 12 |
| Voiceover segments ready | 0 / 26 |
| Estimated length (from current timings) | 6.1 min (target 10.5 min) |
| Script words | 836 (5.57-6.43 min at 150-130 wpm) |

## Estimated cost per stage

Prices from config/costs.yaml (verified: false).

| Stage | Provider | Units (all) | Est. total | Units still to generate | Est. remaining |
|---|---|---|---|---|---|
| image_generate | openart | 26 image | UNKNOWN | 26 image | UNKNOWN |
| motion_generate | openart | 60 second | UNKNOWN | 60 second | UNKNOWN |
| voiceover | viewmax | 4.721 1k chars | UNKNOWN | 4.721 1k chars | UNKNOWN |

## Estimated cost per provider

| Provider | Est. total | Est. remaining |
|---|---|---|
| openart | 0.00 USD + UNKNOWN items | 0.00 USD + UNKNOWN items |
| viewmax | 0.00 USD + UNKNOWN items | 0.00 USD + UNKNOWN items |

## Fact check

- [VERIFY] tags in script: 12
- Unverified facts in topic.yaml: 20 of 20
- Shots whose narration has [VERIFY]: 10
- Publishing requires `script_check --publish` to pass.

  - Livyatan melvillei was formally described in 2010 by Olivier Lambert and colleagues in Nature. (source: Lambert et al. (2010), 'The giant bite of a new raptorial sperm whale from the Miocene epoch of Peru', Nature 466:105-108, doi:10.1038/nature09067 (TODO: confirm))
  - The holotype skull was found in 2008 at Cerro Colorado, Pisco Formation, southern Peru. (source: Lambert et al. (2010) (TODO: confirm year and locality))
  - The fossil is about 9.9-8.9 million years old (late Miocene), revised from an earlier estimate of about 12-13 million years. (source: TODO: find the dating revision paper)
  - The skull is about 3 m (10 ft) long. (source: Lambert et al. (2010) (TODO: confirm))
  - The largest teeth exceed 36 cm (14 in), among the largest biting teeth of any known animal, excluding tusks. (source: Lambert et al. (2010) (TODO: confirm figure and wording))
  - Body length is estimated at 13.5-17.5 m (44-57 ft). (source: Lambert et al. (2010) (TODO: confirm))
  - The genus was first named Leviathan but renamed Livyatan because Leviathan was already used for a mastodon. (source: TODO: Lambert et al. (2010) corrigendum, Nature)
  - The species name honours Herman Melville, author of Moby-Dick. (source: Lambert et al. (2010) (TODO: confirm))
  - Unlike the modern sperm whale, Livyatan had large functional teeth in both upper and lower jaws. (source: TODO)
  - Its skull has a large supracranial basin, suggesting a spermaceti organ. (source: TODO)
  - Likely prey were medium-sized baleen whales of roughly 7-10 m (23-33 ft). (source: TODO)
  - Megalodon teeth occur in the same Pisco Formation deposits and era. (source: TODO)
  - Raptorial sperm whale teeth possibly attributable to Livyatan are known from Chile, South Africa and Australia. (source: TODO)
  - Late Miocene cooling and changes in baleen whale prey may have contributed to its extinction (hypothesis). (source: TODO)
  - The aquatic sloth Thalassocnus is known from the Pisco Formation. (source: TODO)
  - There was no ice at the poles about 13 million years ago. (source: TODO: likely wrong; Antarctic ice sheet existed through the Miocene)
  - Livyatan is nicknamed the 'megatooth whale'. (source: TODO)
  - Bite marks on fossil whale bones have been attributed to Livyatan. (source: TODO)
  - Livyatan disappeared around five million years ago. (source: TODO)
  - A standard US school bus is about 12 m (40 ft) long. (source: TODO)

## Manifest

- Valid: yes; ready for edit: no (assets still planned)

## Next steps (paid stages need approval)

```
python -m pipeline image_generate --topic livyatan --dry-run    # review plan
python -m pipeline image_generate --topic livyatan --approve
python -m pipeline motion_generate --topic livyatan --approve
python -m pipeline voiceover --topic livyatan --approve [--accent uk]
python -m pipeline manifest --topic livyatan
```
