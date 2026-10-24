# Pitfalls Research

**Domain:** Faceless, non-clinician ADHD/autism short-form education account (TikTok first, plus YouTube Shorts and Instagram Reels). Austrian operator. Validation comes first; monetization and automation come later.
**Researched:** 2026-10-24
**Confidence:** MEDIUM overall.
- HIGH: platform API constraints, YouTube's inauthentic-content policy, the EU AI Act Art. 50 dates.
- MEDIUM: Creator Rewards eligibility, the Austrian Impressum mechanics, community-language norms.
- LOW: exact Creator Rewards country list for Austria, specific keyword-suppression behaviour (TikTok doesn't publish it).

> Not legal advice. The Austrian items below are for building a checklist only. Confirm them with WKO, a Steuerberater or a media lawyer before monetization.

---

## Critical Pitfalls

### Pitfall 1: The hook drifts away from the source after fact-checking ("claim drift")

**What goes wrong:**
The script is fact-checked, and then the hook, on-screen text, caption or voice-over gets "punched up". Common shifts:
- "Some people with ADHD may experience…" becomes "ADHD people do X".
- "is associated with" becomes "causes".
- One small study becomes "studies show".
- A finding in children becomes a claim about adults.
- A strength framed as a hypothesis becomes a fact.

The published video then says something no source supports, while the caption still lists real sources. That pairing (real citation, overstated claim) is the worst outcome for a "sources shown" account, because it looks like deliberate misrepresentation.

**Why it happens:**
Hooks are written last and tuned for retention, while the fact-check runs on the draft body. Recording ad-libs aren't in the script at all. LLM rewrites also tend to drop hedges; hedges are the first words cut for length.

**How to avoid:**
- Fact-check the **final artifact**: transcript of the actual recording (Whisper) + on-screen text + caption + hook. Do not fact-check the draft.
- Every factual sentence has to map to a quoted source sentence.
- Hedge words are a checked field. The fact-checker flags any claim whose certainty is higher than the source's (associated→causes, may→does, some→all, small study→"research shows").
- Use a fixed hedging vocabulary in the style guide ("manche", "häufig", "Studien deuten darauf hin", "some people", "research suggests").
- No re-edit after the check. Any change sends the video back to the check.

**Warning signs:**
- Comments say "source?" or "that's not what the study says".
- The hook contains absolutes ("every", "always", "the real reason").
- The recorded audio has sentences that aren't in the script.

**Phase to address:** Script helper + adversarial fact-check (M1). The style guide sets the hedge vocabulary. In M2, the Telegram approve card should show the final transcript, not the draft.

---

### Pitfall 2: The LLM invents citations or attaches real citations to the wrong claim

**What goes wrong:**
Claude produces a plausible DOI, author, year or journal that doesn't exist. Or it cites a real paper for a claim the paper doesn't make, or gives a prevalence number from memory. Prevalence numbers drift a lot: ADHD in adults is anywhere from 2.5% to 6.8% depending on definition, and autism prevalence numbers are US CDC figures that don't apply to Austria. A second LLM asked to "verify" will often agree with the first.

**Why it happens:**
- Generation isn't restricted to retrieved text.
- The adversarial pass gets the same context and the same blind spots.
- Abstracts get cited for claims that only appear in a press release or a pop-science article.

**How to avoid:**
- **Retrieval-first, closed-book drafting.** The script prompt gets only the retrieved passages (PubMed abstract or full text, AWMF S3 guideline sections, Cochrane/meta-analysis text). Each claim has to cite a passage ID.
- **Verify identifiers mechanically, not with an LLM.** Check every DOI/PMID against Crossref/PubMed (title + first author + year must match). If it doesn't resolve, the citation is rejected.
- Have the verifier quote the exact supporting sentence. The operator reviews claim ↔ sentence pairs, not just a "verified" flag.
- Prefer guideline and review sources over single primary studies. Mark single-study claims as such in the script.
- Keep numbers out of scripts unless they're quoted verbatim with the population stated ("in Deutschland, Erwachsene, laut S3-Leitlinie…").
- Check the S3 guideline's version and validity date. Some AWMF guidelines are "abgelaufen" (expired) or under revision, so record the version and date.

**Warning signs:**
- A citation has no URL or no PMID.
- The quoted sentence doesn't literally contain the claim's key term.
- The same paper supports four unrelated claims.
- A number appears with no population or country attached.

**Phase to address:** Script helper + fact-check tooling (M1, before video 1). Treat this as the gate the rest depends on.

---

### Pitfall 3: Medical-misinformation and mental-health enforcement suppresses reach (often silently)

**What goes wrong:**
Videos get marked "ineligible for For You feed", age-restricted, labelled or removed. On TikTok this usually shows up as a reach collapse with no strike. TikTok's community guidelines make content ineligible for the FYF when it contains misinformation with "moderate or greater harm", when it is unoriginal or reused, or when it shows inauthentic engagement signals. YouTube removes content that contradicts local health authorities or WHO guidance in its Prevention/Treatment/Denial categories. Medication claims (stimulants), "cure" or "treatment" claims, and "you don't need meds" style content are the most exposed.

Self-harm adjacency is a separate trigger. ADHD and autism content near suicide, self-harm, eating disorders or burnout ("autistic burnout made me want to…") can trigger sensitive-content handling or search interventions.

**Why it happens:**
- Classifiers work on keywords and visuals, not context.
- An educational framing doesn't reliably protect a video.
- Under-18 viewers trigger stricter treatment. Parent and teen topics bring under-18 viewers.

**How to avoid:**
- Keep the conservative whitelist: no medication, no diagnosis, no ABA, no "is my child autistic?". The PROJECT already has it. Also add these to the blacklist:
  - suicide/self-harm statistics
  - eating disorders
  - "treatment" or "cure" verbs
  - supplements and diet-as-treatment
  - "doctors won't tell you"
  - comparisons to vaccines or other contested topics
- Use "Unterstützung", "Strategien" and "Umfeld" instead of "Behandlung"/"Therapie" unless you're quoting the guideline.
- Never state or imply that a professional diagnosis or treatment is unnecessary. The disclaimer "Kein Ersatz für ärztliche/psychotherapeutische Beratung" goes in the caption or bio.
- Avoid self-diagnosis checklist formats ("5 signs you have ADHD"). They are the main misinformation pattern platforms and researchers target.
- Log each video's FYF eligibility state. In TikTok analytics a video can show as "not eligible for recommendation" when you check its status, so check it per video.

**Warning signs:**
- One video's views drop near zero while others are normal.
- The "For You" share of traffic sources falls.
- An "unverified content" banner appears.
- The video is age-restricted.
- YouTube shows a limited-ads ($ yellow) icon.

**Phase to address:** Style guide + whitelist/blacklist (M1). Add a per-video FYF/eligibility field to the metrics log (M1). This is required, or the validation readout will mix "bad format" with "suppressed video".

**Confidence:** MEDIUM. The policy categories were checked against TikTok's community guidelines page and YouTube's medical misinformation policy coverage. The exact keyword behaviour is undocumented, and most of what circulates about it is creator folklore.

---

### Pitfall 4: Feeding the self-diagnosis problem (the "everyone has ADHD" backlash)

**What goes wrong:**
Relatable "ADHD trait" content describes normal human experiences as symptoms. The PLOS ONE study by Karasavva et al. (2025) rated the top 100 #ADHD TikToks: only 48.7% of their claims matched DSM criteria, and 68.5% of the inaccurate ones described "normal human experience". Watching those videos reinforced self-diagnosis. Clinicians, journalists and critical ND creators specifically call out such accounts. For an account whose whole moat is credibility, being classified as "another ADHD-TikTok misinformation account" is fatal, and the "Challenge + science" pillar is exactly where this happens.

**Why it happens:**
- Relatability gets engagement, and "This is so me" comments get rewarded.
- Pillar 1's template ("Some people with ADHD experience X") turns into a symptom list when X is common (procrastination, losing keys).

**How to avoid:**
- For every "X", state what makes it clinically different: frequency, pervasiveness, impairment, and onset in childhood.
- Add a standing line where it fits: "Das allein heißt nicht, dass man ADHS hat."
- Prefer mechanism content (executive function, reward sensitivity, sensory processing) over trait lists.
- Track "is this me?" comments as a risk signal, not a success signal.

**Warning signs:**
- The comments are mostly "so I have ADHD?".
- Stitches or duets from clinicians criticise the video.
- Saves are high while follows are low (people treat it as a symptom checklist).

**Phase to address:** Style guide + content matrix (M1). Add a fact-check rule for "trait vs. criterion".

---

### Pitfall 5: Language and framing backlash in ND communities

**What goes wrong:**
One clip with the wrong framing gets stitched and dog-piled. These are the high-risk framings:
- **Functioning labels** ("high-functioning", "hochfunktional", "leichter Autismus", "low-functioning"). Most autistic self-advocates reject them.
- **"Superpower" framing.** Many ADHD/autistic people experience it as dismissive of real disability and impairment. Pillar 2 (strengths) is exposed here.
- **Pathologizing or deficit framing** ("suffers from", "leidet an Autismus", "Krankheit", "heilen", "Autismus bekämpfen").
- **ABA or "therapy to reduce stimming"**, compliance-based parenting tips, and "how to stop meltdowns" framed as behaviour to remove. The parent pillar is where this lands accidentally: a "how to handle a meltdown" video read as "how to suppress your child's autistic traits" is a common blow-up.
- **Person-first vs identity-first.** English autistic communities largely prefer "autistic person". Parent and clinical audiences often use "person with autism". In German, many self-advocates use "Autist:in/Autist*in" or "autistische Menschen", while guidelines and parent associations often use "Menschen mit Autismus(-Spektrum-Störung)".
- **Outdated terms:** "Asperger" (dropped in ICD-11 and DSM-5; it also has a Nazi-era history: Hans Asperger), "Autismus-Spektrum-Störung" vs "Autismus-Spektrum", and "AD(H)S/ADS" as separate conditions.
- **Gendered "female autism/ADHD is different" claims.** The research is contested, and they're often oversimplified.
- **Speaking for autistic people as a presumably non-autistic man.** If the operator isn't ND, "translator of research" helps, but parent-centric content has to avoid making the parent the victim.
- **German specifics.** The DACH discourse distinguishes self-advocacy organisations (e.g. Aspies e.V., autistic-led blogs/accounts) from parent/professional associations (e.g. Autismus Deutschland e.V.). Citing only the latter can read as taking a side. The German neurodiversity community is smaller and more tightly networked than the English one, so one controversy spreads further proportionally.

**Why it happens:**
- Clinical sources (S3 guidelines, DSM, ICD) use deficit language: "Störung", "Defizit".
- Translating the research faithfully imports that language into community-facing content.
- LLMs default to person-first clinical phrasing.

**How to avoid:**
- Write a terminology table in the style guide (DE + EN) with preferred, acceptable and never columns. Lint every script against it automatically.
- Default to identity-first ("autistische Menschen", "autistic people") with occasional person-first, and say so if asked. When quoting a guideline, quote it as a quote.
- Frame strengths as "manche berichten / research on X finds… alongside real challenges". Never "superpower".
- For the parent pillar: aim at the child's needs, regulation and co-regulation, and understanding. Never at extinguishing traits. Blacklist "stop stimming" or "get them to make eye contact".
- Before posting, ask two or three ND reviewers (autistic + ADHD adults, ideally German-speaking) to review the style guide once. Ask them again for any parent-pillar video in the first batch.

**Warning signs:**
- Comments contain "functioning labels", "ABA", "ableist", "pathologisierend", "Elternperspektive".
- A stitch from an ND creator is getting more views than the original.

**Phase to address:** Style guide + terminology table (M1, before the first video). The fact-check/lint pass enforces it (M1). The competitor scan (M1) should record each top account's terminology choices as a reference.

**Confidence:** MEDIUM. Based on well-established community norms and surveys (e.g. Kenny et al. 2016 and later terminology surveys). Individual preferences vary, and parent audiences differ.

---

### Pitfall 6: Drawing conclusions from 20–30 videos on a new account (validation noise)

**What goes wrong:**
The go/no-go picks "winning formats" that were really luck:
- One video got a lucky distribution batch.
- The hook was strong but the pillar wasn't.
- The posting time or a trend sound coincided.
- New-account distribution noise: early videos get small, variable test audiences, and one viral video changes who sees the next few.

Twenty to thirty videos across four pillars × several angles × hooks is about 1–3 videos per cell. View counts are heavy-tailed, so medians over three videos mean little. Milestone 2 then automates a format that doesn't actually perform.

**Why it happens:**
- Too many variables are changed at once.
- Views get used as the outcome.
- Chronological confounding: later videos benefit from a bigger follower base, and the operator's skill improves over time.

**How to avoid:**
- **Pre-register** the readout: metrics, comparison rule and minimum videos per cell, written before posting video 1.
- **Cut the factor space.** Test pillar, holding hook style roughly constant. Then test hook within the winning pillar. Aim for ≥4–5 videos per compared cell. With 20–30 videos that means comparing about four to six cells, not twenty.
- Use **rate metrics**: watch-through/average percentage watched, 2-second/3-second hold, shares per 1k views, saves per 1k views, follows per 1k views. Don't use raw views.
- Use **rank-based comparisons**. Count how often a cell beats the account's running median, and interleave pillars (round-robin or randomized order) so time trends spread evenly.
- Record confounders per video: posting hour, length, sound, recording quality, FYF eligibility (see Pitfall 3) and whether it was cross-posted first.
- Treat the result as **directional**. The readout should be one of "clear winner", "no difference detected" or "need N more". "No difference" is a legitimate outcome.
- Don't automate (M2) on a single viral outlier. Require replication: the winning format wins again in a fresh batch of 5–10.

**Warning signs:**
- One video holds most of the account's total views.
- The "winner" is always the most recent pillar.
- The readout relies on views.

**Phase to address:** Metrics log + go/no-go readout design (M1). Write the readout rule before the first post.

---

### Pitfall 7: Assuming Creator Rewards (or any platform payout) is available in Austria, or fits the format

**What goes wrong:**
The monetization plan counts on TikTok Creator Rewards. Several facts cut against that:
- **Austria doesn't appear in available lists of eligible countries.** Third-party trackers (2026) list the US, UK, Germany, France, Japan, South Korea, Brazil and Mexico, and say Austria has LIVE gifts but not Creator Rewards. TikTok's EEA program terms say only "available only in selected countries", depending on country of residence. **VPN use is explicitly prohibited** (it gets accounts banned).
- **Rewards only pay for videos longer than 1 minute.** Other requirements: 18+, 10,000 authentic followers, 100,000 authentic views in the last 30 days, a personal (not Business) account in good standing, original content, and 1,000 qualified FYF views per video before it starts earning. Duets, Stitches, Photo Mode and paid promotions are excluded.
- **Converting to a Business account** (to unlock commercial-music restrictions, analytics or scheduling) disqualifies the account from Creator Rewards.
- The 60–75 s script target crosses the 1-minute threshold, which helps. But very short hooks-only formats (<60 s) earn nothing even if eligible.
- YouTube Partner Program (Shorts revenue share) **is** available in Austria, but the July 2025 "inauthentic content" (mass-produced, templated) policy applies (see Pitfall 8). Instagram's Reels payout programs have historically been invite-only or US-centric.

**Why it happens:**
Creator-economy advice is US-centric, and a German creator's eligibility doesn't mean an Austrian resident is eligible.

**How to avoid:**
- Verify Austria eligibility in-app (Creator tools → Creator Rewards) at the legal-checklist step. Plan monetization around own digital products and sponsorships/affiliates (already in PROJECT), with YouTube revenue share as the only platform payout you can count on.
- Keep the TikTok account **Personal**, not Business.
- Keep the eligible format ≥61 s if Rewards ever opens in AT.
- Don't model revenue on Rewards RPMs.

**Warning signs:** Creator Rewards doesn't appear in Creator tools. Monetization plans cite US RPM figures.

**Phase to address:** Legal/tax checklist (M1). Account setup on day 1 (Personal account). The "60–75 s" length decision is already in the script spec.

**Confidence:** Austria not eligible: LOW–MEDIUM (third-party lists, official terms don't enumerate countries). The 1-min/10k/100k/18+ requirements: MEDIUM–HIGH (official terms + multiple sources).

---

### Pitfall 8: Automation that triggers "unoriginal / inauthentic / AI" penalties (M2)

**What goes wrong:**
A fully automated Remotion pipeline (same template, stock B-roll, TTS fallback, Whisper captions) produces videos that are "made with a template with little to no variation" and "easily replicable at scale". Those are the words of YouTube's July 2025 inauthentic-content YPP policy. TikTok makes "unoriginal or reused material without novel additions" ineligible for the FYF, and Creator Rewards requires original content.

AI voice or realistic AI visuals that aren't labelled can be removed, restricted or labelled by TikTok. EU AI Act Art. 50, applicable from 2 Aug 2026, requires disclosing deepfakes and AI-generated public-interest text. There's an exemption when a person has done editorial review and takes responsibility. The operator-review gate supports that, but only if the review is real and documented.

The faceless format makes all of this more likely, because the only "author signal" is the voice.

**Why it happens:**
"Automate production" gradually becomes "automate everything that makes it look human". TTS fallback becomes the default once the operator is busy.

**How to avoid:**
- Keep the operator's real voice mandatory for anything published. TTS is only for drafts and previews, and if TTS ever ships, label it with TikTok's AI-generated content toggle (the API has an AIGC flag) and YouTube's altered/synthetic disclosure.
- Build several visual templates and rotate them. Use per-video custom elements (diagrams of the actual mechanism, the real source shown on screen).
- Don't cross-post with the TikTok watermark. Export clean masters for Shorts/Reels.
- Log each review approval (who, when, which transcript version). That's evidence of human editorial control.

**Warning signs:**
- YPP application rejected for "reused/inauthentic content".
- Reach drops across all videos after automation starts.
- Viewers comment "AI voice"/"bot account".

**Phase to address:** M2 architecture design. Add the AI-labeling rules to the M1 legal checklist.

**Confidence:** HIGH for the YouTube policy and AI Act dates. MEDIUM for how TikTok enforces originality in practice.

---

### Pitfall 9: Austrian Impressum/disclosure, health-advertising and trade-law gaps (faceless ≠ anonymous)

**What goes wrong:**
Faceless is read as anonymous, and that runs into several Austrian rules:
- **MedienG §25 (Offenlegung).** Every social media profile used to publish content regularly counts as a medium. You must disclose the media owner (name, place of residence or registered office, business purpose/editorial line). For a "small" medium three items suffice, reachable within two clicks (bio link).
- **ECG §5.** Once the activity is commercial (gainful, which monetization makes it), stricter provider information applies: name, geographic address, contact (email), plus trade/registration data if applicable.
- That puts a real name and possibly a home address in public. For a faceless health account, that's a doxxing and harassment risk.
- **Advertising/health claims, at the monetization step:**
  - **UWG**: misleading commercial practices, including undisclosed sponsorship.
  - **MedienG §26**: paid content must be labelled "Anzeige/Werbung".
  - **EU Health Claims Regulation 1924/2006**: health claims for *foods/supplements*, which matters if any sponsor sells supplements or nutrition. PROJECT already excludes this.
  - **AMG §§50ff**: medicinal-product advertising. Never promote medication; a stimulant brand mention alone can count as advertising.
  - For German viewers, **HWG (Heilmittelwerbegesetz)** can apply to ads aimed at Germany. It is strict about advertising for treatments and about "fear-based" health ads.
  - App sponsors that claim to "treat ADHD" (DiGA-type apps are medical devices) carry medical-device advertising rules.
- **Protected titles and regulated trades.** "Psychologe/Psychologin" (Psychologengesetz 2013) and "Psychotherapeut:in" (Psychotherapiegesetz) are protected titles in Austria. Paid individual advice or coaching for parents falls under the regulated trade **Lebens- und Sozialberatung** (reglementiertes Gewerbe, requires a qualification). Selling one-to-one "ADHD parent coaching" without that is a violation. Selling PDF guides is a different trade question (generally freier Gewerbe/neuer Selbständiger), so check with WKO.
- **Tax:** register with the Finanzamt once there's income. Kleinunternehmerregelung (VAT small-business threshold; €55,000 since 2025), Einkommensteuer, and possibly SVS insurance as a Neue/r Selbständige/r. Platform payouts from Ireland/US entities need correct reverse-charge handling.

**Why it happens:**
Creator guides are German (DE TMG/DDG) or US based. Austrian law is different and less often written about.

**How to avoid:**
- Before publicly launching (not just before monetization), put a MedienG §25 disclosure in the bio link. MedienG applies from the first regular publication, not from the first euro.
- Use an Impressum/address service or business address if the home address isn't acceptable. Confirm with WKO that such an address is valid "ladungsfähig/geographisch" for ECG.
- Write a checklist: §25 now → ECG §5 + trade/tax registration at monetization → labelling rules for sponsored content → per-sponsor screening (no meds, supplements, telehealth or "treats ADHD" claims).
- Never use "Psychologe", "Therapeut" or "Coach für ADHS" titles. Use "Ich lese Forschung und übersetze sie", which PROJECT already has.

**Warning signs:**
- No disclosure link in the bio at launch.
- A sponsor offers money for an app claiming clinical outcomes.
- Plans for "1:1 calls with parents".

**Phase to address:** Legal checklist (M1). Split it into a **pre-launch** item (§25 disclosure) and **pre-monetization** items (everything else). The PROJECT currently gates the whole checklist on monetization; the §25 item should move earlier.

**Confidence:** MEDIUM. WKO and multiple Austrian legal-blog sources agree on §25/ECG for social profiles. The trade and title rules come from known statutes but need WKO confirmation.

---

### Pitfall 10: Comment sections become a crisis and liability surface

**What goes wrong:**
Mental-health content draws:
- disclosures of suicidality or self-harm
- parents describing abuse or crisis situations
- requests for diagnosis or medication advice ("Hab ich ADHS?", "Soll mein Kind Medikinet nehmen?")
- harassment and ableist trolls, community pile-ons, and spam/scam DMs (fake "ADHD test" links)

A faceless account with one operator spending 30–60 min a day can't triage at scale. An unanswered crisis comment, or a hasty reply that sounds like advice, is both a harm and a reputation risk. Replying "it sounds like you have ADHD" is diagnostic.

**Why it happens:**
Comment volume grows non-linearly after one viral video, and no plan exists for that day.

**How to avoid:**
- Write a crisis-response playbook before posting:
  - Canned, non-diagnostic, human-written replies (never auto-sent) for crisis disclosures. They point to: Austria — Telefonseelsorge 142, Rat auf Draht 147 (children/youth/parents), emergency 144/112. Germany — TelefonSeelsorge 0800 111 0 111 / 0800 111 0 222. Use the platform's in-app reporting for imminent risk.
  - A standard "Ich kann keine Diagnosen stellen; Anlaufstellen: …" reply for diagnosis requests.
- Turn on platform keyword filters: slurs, scam-link patterns, "DM me for diagnosis". Use "filter all comments" during spikes.
- Pin a comment with the sources plus a short "not a diagnosis" line and crisis resources on sensitive topics.
- Set a spike protocol: if a video passes ~10× median views, do a 2× daily comment sweep for 72 h, or temporarily restrict comments.
- No DMs for advice. Set DMs to restricted.
- In M2: don't auto-reply (already decided). An LLM *flagging* crisis comments into the Telegram review queue is fine. An LLM *replying* is not.

**Warning signs:** Unread comments on viral videos. Advice requests in DMs. Duplicate scam comments.

**Phase to address:** Playbook in M1, before the first post. Crisis-flagging tooling is optional in M2.

---

### Pitfall 11: Burnout from daily posting (and the validation plan quietly stalls)

**What goes wrong:**
About one video a day at 30–60 min a day underestimates the real cost: research + fact-check review + recording + editing + posting + comments + metrics log. That's often 60–120 min for a sourced health video. The operator skips the fact-check "just this once" (see Pitfall 1), posts irregularly, or stops around video 12. The result is an incomplete validation that can't be interpreted.

**Why it happens:**
Daily-posting folklore, and the fact-check overhead per video that a source-first account carries and generic creators don't.

**How to avoid:**
- Batch: research and script 5–7 on one day, record in one session, schedule them natively in the TikTok app (works without the API).
- Post 4–5 per week rather than daily. Validation needs 20–30 *comparable* videos, not 30 consecutive days.
- Time each stage per video in the metrics log, so M2 automation targets the real bottleneck.
- Allow a "fallback week" with no new topics, only re-cuts.

**Warning signs:** Fact-check pairs skimmed in under a minute. Backlog empty on posting day. Gaps longer than 3 days.

**Phase to address:** M1 planning (cadence decision) and the metrics log (time-per-stage field).

---

### Pitfall 12: The TikTok Content Posting API audit blocks M2 publishing

**What goes wrong:**
M2 assumes scheduler-API auto-publish. An **unaudited** TikTok API client can only post with `SELF_ONLY` visibility, for at most 5 users in 24 h, and the posting account must be private. Posting to a public account from an unaudited client errors out. The audit requires a compliant UX under TikTok's Content Sharing Guidelines:
- show the creator's nickname
- let the user choose the privacy level (no defaults hidden from them)
- disclosures for commercial content
- explicit consent before posting
- no adding watermarks/promotional branding

A personal single-account tool may struggle to justify the audit.

**Why it happens:**
"Just use the API" planning, without reading TikTok's developer Content Sharing Guidelines.

**How to avoid:**
- For M2, publish through an already-audited third-party scheduler (Metricool, Buffer, Blotato), or use TikTok's "upload to inbox/draft" flow where the operator taps publish in-app. The draft flow also keeps a human publish step, which fits "automate production, not judgment".
- Only build a direct-post integration if there's a reason to go through the audit. Plan weeks, not days.
- Check how each scheduler handles the AI-content flag and commercial-content disclosure flags.

**Warning signs:** Uploads succeed but videos are private-only. Error codes about unaudited clients.

**Phase to address:** M2 architecture (publishing component). Prototype the publish path first in M2, before investing in render polish.

**Confidence:** HIGH (TikTok developer docs + multiple consistent guides).

---

### Pitfall 13: Consent and privacy failures with lived-experience stories and audience data

**What goes wrong:**
"Anonymized" stories from the operator's circle are recognisable to that circle: specific incidents, place, child's age plus school situation, voice. Children's stories told without the child's assent. Health data is GDPR special-category data (Art. 9). An email list or parent-guide sales that collect "my child has ADHD" data become a processing obligation. Facelessness also fails through background audio, reflections or metadata.

**How to avoid:**
- Get written consent per story. Change identifying details. Never use children's real voices or names. Let the contributor see the script before publishing.
- Keep a minimal data policy: no health questions in email sign-up forms, and a GDPR privacy notice before collecting any data at all (M2/monetization).
- Faceless hygiene: check recordings for room audio, reflections and EXIF.

**Phase to address:** M1 style guide (consent rule) and the legal checklist (GDPR at monetization).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fact-checking the draft instead of the final transcript | Faster review | Claim drift goes out under real citations (Pitfall 1) | Never |
| LLM-only citation verification (no DOI/PMID resolve) | No API plumbing | Hallucinated references reach captions | Never. Crossref/PubMed lookups are free |
| Sources in a free-text caption with no stored record | Quick | Can't audit later or answer "source?" consistently. M2 can't reuse it | Only for videos 1–5. Then store claim↔source pairs in SQLite |
| Metrics logged manually in a spreadsheet without FYF status or confounders | Fast start | The readout can't separate suppression or timing from format quality | Spreadsheet is fine. Leaving out the fields is not |
| One Remotion template for everything | Ship M2 faster | "Inauthentic/templated content" demonetization | Only while unmonetized and testing |
| TTS "fallback" in production | Keeps the cadence | AI-label duty, authenticity loss, inauthentic-content risk | Unpublished previews only |
| Business TikTok account for scheduling | Scheduler features | Disqualifies Creator Rewards | Never, unless deliberately giving up Rewards |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| TikTok Content Posting API | Expecting public posts before the audit | Unaudited = SELF_ONLY, private account, 5 users/24 h. Use the inbox/draft flow or an audited scheduler |
| PubMed / Crossref | Trusting LLM-provided IDs | Resolve every ID. Match title + first author + year |
| AWMF S3 guidelines | Citing an expired or replaced version | Store guideline register number, version and "gültig bis". Re-check quarterly |
| Whisper (German) | Mis-transcribing medical terms ("ADHS" → "ADS", drug names, "exekutive Funktionen") and Austrian pronunciation | Use a domain vocabulary prompt or initial prompt. Operator proofreads captions. Captions are part of the claims and go through the fact-check |
| Cross-posting to Reels/Shorts | Uploading the TikTok-watermarked export | Export a clean master. Instagram deprioritises visible watermarks from other platforms (widely reported, MEDIUM) |
| Schedulers (Metricool/Buffer/Blotato) | Assuming they set AI-content / branded-content flags | Check per scheduler. Otherwise set them manually in-app |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Comment volume after a viral hit | Unread crisis comments, pile-on | Spike protocol, keyword filters, comment restriction | First video at ~10× median views |
| Manual fact-check review per video | Review skimmed, cadence slips | Claim↔sentence pairs sorted by risk (numbers and causal claims first) | Around 5+ videos/week |
| Topic matrix exhaustion within the whitelist | Repetitive topics, falling retention | Expand the whitelist deliberately and document why; add angles not claims | ~60–100 videos |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Home address in the Impressum of a controversial health account | Doxxing, harassment of the faceless operator | Address service/business address (WKO-confirmed validity) |
| No 2FA on TikTok/YouTube/Meta accounts | Takeover. Health accounts are targeted to post scam "ADHD test/supplement" links | 2FA via an authenticator app, unique passwords, recovery codes stored offline |
| Scheduler/API tokens on the shared polymarkt-watch host | Token leak means public posting under your name. (The sibling project had a Safe drain on 2026-10-21 via a path-traversal leak of env vars.) | Separate container/user, secrets not in env dumps, no publicly bound web UI, least-privilege scopes |
| Scam comments impersonating the account ("DM me for a test") | Audience harm, reputation | Comment filters on handle-similar names, regular pinned warning |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Sources as "link in bio" or a bare DOI list | ND viewers and parents can't check; looks performative | Short readable citation in the pinned comment (author, year, type: "Übersichtsarbeit", "S3-Leitlinie") + on-screen "Quelle" frame |
| Overloaded captions and fast cuts | ND audience overstimulated, accessibility complaints | Clean captions, steady pacing, no flashing |
| Disclaimers that sound defensive or clinical | Feels cold, reduces trust | One consistent, warm line plus the resources |
| Parent content that frames the child as the problem | Alienates ND adults, causes backlash | Child-needs framing. Have ND reviewers check the parent pillar |

## "Looks Done But Isn't" Checklist

- [ ] **Fact-check:** ran on the *final recorded transcript + on-screen text + caption*. Check: transcript hash matches the reviewed version.
- [ ] **Citations:** every DOI/PMID resolves, and title/author/year match. Check: an automated resolve log exists for the video.
- [ ] **Hedges:** no certainty upgrade vs source. Check: the verifier's "certainty" column is all "equal or weaker".
- [ ] **Terminology:** lint against the DE/EN term table passes (no functioning labels, "leidet an", "Superkraft", "Asperger" outside quotes).
- [ ] **Metrics log:** includes FYF eligibility, posting time, length, sound, pillar, hook type, time spent per stage.
- [ ] **Validation readout:** rule written down before video 1. ≥4–5 videos per compared cell.
- [ ] **Launch legal:** MedienG §25 disclosure link in the bio of every platform at the first post.
- [ ] **Account type:** TikTok is a Personal account (Creator Rewards eligibility).
- [ ] **Crisis playbook:** AT + DE hotlines written into canned replies. Spike protocol defined.
- [ ] **Consent:** written consent on file for every lived-experience story.
- [ ] **M2 publishing:** the publish path is tested with a public post, not just a SELF_ONLY one.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong claim or citation published | MEDIUM | Delete or correct within hours. Post a correction video/pinned comment naming the error. Log the root cause and add a rule to the fact-checker |
| Community pile-on over framing | MEDIUM–HIGH | Don't argue in comments. Short, specific acknowledgement + changed terminology. Talk directly with the critic if they're an ND creator. Avoid a defensive "I'm just translating research" |
| Video suppressed or removed | LOW–MEDIUM | Appeal in-app. Mark it "suppressed" in the metrics log and exclude it from the readout. Check for blacklist words |
| Strike accumulation on YouTube | HIGH | Pause the topic area. Review guidelines. Don't post in the same category until the strike expires (90 days) |
| Impressum non-compliance discovered | LOW | Add the disclosure immediately. Penalties typically follow a failure to fix |
| Account takeover | HIGH | Platform recovery flow, recovery codes, warn followers through the other platforms |
| Burnout stall | LOW | Drop to 3/week. Finish the validation with fewer, comparable videos rather than abandoning it |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Claim drift | M1 fact-check tooling + style guide | Fact-check input is the final transcript. No post-check edits |
| 2 Hallucinated citations | M1 script helper (retrieval-first) + mechanical ID resolve | 100% of IDs resolve. Operator signs off claim↔sentence pairs |
| 3 Platform enforcement/suppression | M1 whitelist/blacklist + metrics log FYF field | Suppressed videos are flagged and excluded from the readout |
| 4 Self-diagnosis amplification | M1 style guide ("trait vs criterion" rule) | No checklist-format videos. Comments are not dominated by "do I have it?" |
| 5 ND-community framing | M1 terminology table + ND reviewer pass | Lint passes. Reviewers signed off the style guide |
| 6 Small-sample validation noise | M1 metrics/readout design (pre-registered) | Readout rule committed before video 1. ≥4–5 per cell. Replication before M2 |
| 7 Creator Rewards assumptions | M1 legal/monetization checklist + Personal account setup | In-app eligibility checked in Austria. Revenue plan doesn't depend on Rewards |
| 8 Inauthentic/AI penalties | M2 architecture + M1 AI-labeling checklist item | Own voice on all published videos. Template variety. AIGC flags set where applicable |
| 9 Austrian legal gaps | M1 checklist, split into pre-launch (§25) and pre-monetization (ECG, trade, tax, ads) | Disclosure live at video 1. WKO/Steuerberater confirmation before the first euro |
| 10 Comment crisis | M1 playbook before the first post | Canned replies + hotlines exist. Spike protocol documented |
| 11 Burnout | M1 cadence decision + time-per-stage logging | Videos 20–30 completed. Fact-check time stays above its floor |
| 12 TikTok API audit | M2 publishing prototype first | A public post via the chosen path succeeds |
| 13 Consent/privacy | M1 style guide + legal checklist (GDPR) | Written consents on file. No health data collected without a notice |

## Sources

- TikTok Community Guidelines, Integrity & Authenticity: FYF ineligibility (moderate-harm misinformation, unoriginal content), AI-generated content labeling. https://www.tiktok.com/community-guidelines/en/integrity-authenticity (fetched 2026-10-24, HIGH)
- TikTok Creator Rewards Program Terms (EEA): selected countries only, 10k followers, 100k views/30d, personal account, originality, no VPN. https://www.tiktok.com/legal/page/global/tiktok-creator-rewards-program-eea/en (fetched, HIGH for requirements; it doesn't list countries)
- Third-party country lists naming Austria as not eligible (LOW–MEDIUM): https://monetizednow.com/creator-rewards-countries, https://quasa.io/media/tiktok-creator-rewards-program-eligible-countries-in-2026, https://creatorsagency.co/blog/tiktok-creator-rewards-program-2026
- TikTok Content Sharing Guidelines (developer): unaudited client = SELF_ONLY, 5 users/24 h, private accounts. https://developers.tiktok.com/docs/en/content-sharing-guidelines ; corroborated by https://www.outstand.so/blog/tiktok-content-posting-api (HIGH)
- YouTube "inauthentic content" YPP update, 15 Jul 2025: https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/ (HIGH)
- YouTube medical misinformation policy (Prevention/Treatment/Denial, contradicting local health authorities or WHO): https://thehill.com/policy/technology/4153540-youtube-announces-new-policies-to-target-medical-misinformation/ (MEDIUM–HIGH)
- Karasavva et al. (2025), PLOS ONE, "A double-edged hashtag": 48.7% of claims in top 100 #ADHD TikToks accurate. https://journals.plos.org/plosone/article/file?id=10.1371%2Fjournal.pone.0319335&type=printable ; https://www.eurekalert.org/news-releases/1076679 (HIGH)
- EU AI Act Art. 50 transparency obligations applicable 2 Aug 2026; Digital Omnibus didn't move Art. 50. https://www.cooley.com/news/insight/2026/2026-08-03-eu-ai-act-transparency-obligations-take-effect-2-august-2026 ; https://artificialintelligenceact.eu/transparency-rules-article-50/ (HIGH)
- WKO, Impressum und Offenlegung: https://www.wko.at/information-consulting/werbung-marktkommunikation/impressum-und-offenlegung ; https://meinlaw.at/impressumspflicht-social-media-rechtsgrundlagen-strafen/ ; https://trustyourwebsite.com/at/de/guides/impressumspflicht-oesterreich (MEDIUM)
- Influencer ad labeling Austria: https://influencermarketingguide.at/themen/content-recht/ (MEDIUM)
- Training-knowledge items to verify (LOW–MEDIUM): Psychologengesetz 2013 / Psychotherapiegesetz title protection; Lebens- und Sozialberatung as a regulated trade; Kleinunternehmer threshold €55k; Austrian hotlines (142, 147, 144) and German TelefonSeelsorge numbers; autism terminology surveys (Kenny et al. 2016, Autism); German self-advocacy vs parent-association discourse.

---
*Pitfalls research for: faceless ND short-form education account (AT operator)*
*Researched: 2026-10-24*
