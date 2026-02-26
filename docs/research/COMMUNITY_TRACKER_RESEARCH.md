# Community ICE Activity Tracker Research
**Last Updated:** February 4, 2026

## Executive Summary

Researched 4 community-driven ICE activity tracking apps/platforms to evaluate for data integration:
- ✅ **1 feasible** (RedadAlertas - open source API)
- ⚠️ **2 require verification** (DryICE, ICE in My Area - no public API found)
- ❌ **1 not viable** (ICEBlock - removed from App Store, no API)

---

## 1. RedadAlertas ✅ RECOMMENDED

### Overview
- **URL:** https://redadalertas.com/
- **GitHub:** https://github.com/Cosecha/redadalertas
- **API Repo:** https://github.com/Cosecha/redadalertas-api
- **Organization:** Movimiento Cosecha (grassroots immigrant rights organization)
- **Purpose:** Real-time, verified alerts of ICE raids delivered securely

### Technical Details
- **Status:** ✅ Open source, actively maintained (266 commits)
- **License:** AGPL-3.0 (allows research/civic use with attribution)
- **API:** Public API available for web and mobile apps
- **Data Flow:** User reports → Rapid response network verification → Verified alerts
- **Privacy:** Privacy-focused, Tor built-in

### API Access
- **Cost:** ✅ FREE (open source)
- **Authentication:** Not clearly documented (needs investigation)
- **Rate Limits:** Not documented
- **Documentation:** Referenced at https://cosecha.github.io/redadalertas-api/ (currently 404)
- **Data Format:** Not documented in public materials

### Feasibility Assessment
**✅ FEASIBLE - High Priority**

**Pros:**
- Open source (AGPL-3.0 license)
- Designed for civic/advocacy purposes
- Verified data (not just crowdsourced)
- Active GitHub repositories
- Public API exists

**Cons:**
- Documentation site returns 404 (may be outdated)
- API endpoints not clearly documented
- May require contacting Cosecha organization
- Verification process may limit signal volume

**Implementation Path:**
1. Fork GitHub repository to understand API structure
2. Review source code for API endpoints
3. Contact Cosecha organization for research access
4. Test API calls to verify functionality
5. Create `redadalertas_scraper.py` if API is accessible

**Estimated Effort:** 6-10 hours (includes research + scraper development)

**Expected Signals:** 10-30/week (verified reports are less frequent but high quality)

**Priority:** Medium-High (excellent data quality but requires API investigation)

### Sources
- [RedadAlertas Website](https://redadalertas.com/)
- [GitHub Repository](https://github.com/Cosecha/redadalertas)
- [API Repository](https://github.com/Cosecha/redadalertas-api)
- [Fast Company Article](https://www.fastcompany.com/3068357/this-app-warns-undocumented-immigrants-when-raids-are-coming)
- [Vice Article](https://www.vice.com/en/article/raid-alerts-wants-to-warn-undocumented-immigrants-with-an-app/)

---

## 2. ICEBlock ❌ NOT VIABLE

### Overview
- **URL:** https://www.iceblock.app/
- **Developer:** Joshua Aaron
- **Purpose:** Real-time ICE sighting reports (Waze-style)
- **Platform:** iOS only
- **Users:** ~20,000 active users (at peak)

### Technical Details
- **Status:** ❌ Removed from App Store (October 2025)
- **Privacy:** Excellent (no user data collection, anonymous reports)
- **Data Retention:** Posts deleted after 4 hours
- **API:** No public API mentioned
- **Network Analysis:** EFF confirmed no geolocation or device tracking

### Removal Context
- Department of Justice urged Apple to remove app (October 2025)
- App still works if already installed
- No official API access available

### Feasibility Assessment
**❌ NOT VIABLE**

**Reasons:**
- No public API available
- App removed from App Store (limited future availability)
- 4-hour data retention window (ephemeral data)
- Government pressure suggests legal/ethical risks
- Anonymous reporting makes verification difficult

**Alternative:** Community ICE tracker apps are controversial. Stick with verified sources (government, news, advocacy organizations).

### Sources
- [ICEBlock Website](https://www.iceblock.app/)
- [CNN Article](https://www.cnn.com/2025/06/30/tech/iceblock-app-trump-immigration-crackdown)
- [TechCrunch Article](https://techcrunch.com/2025/07/01/iceblock-an-app-for-anonymously-reporting-ice-sightings-goes-viral-overnight-after-bondi-criticism/)
- [TIME Article](https://time.com/7298880/iceblock-iphone-app-ice-sightings-backlash/)
- [Apple Gadget Hacks - App Removal](https://apple.gadgethacks.com/news/apple-removes-iceblock-app-after-government-pressure/)

---

## 3. DryICE ⚠️ REQUIRES VERIFICATION

### Overview
- **URL:** https://dryiceapp.com/
- **Type:** Progressive Web App (PWA) + native iOS/Android apps
- **Purpose:** Interactive map of ICE activity
- **Features:** User reports, location data, real-time notifications

### Technical Details
- **Status:** ⚠️ Unknown (website exists but search results conflated with unrelated products)
- **API:** Not found in search results
- **Authentication:** Unknown
- **Cost:** Free core functionality mentioned

### Feasibility Assessment
**⚠️ REQUIRES VERIFICATION**

**Action Required:**
1. Visit dryiceapp.com directly to verify it's the correct app
2. Look for API documentation or developer portal
3. Contact developers for research access
4. Assess legal/ethical implications

**Estimated Research Time:** 1-2 hours

**Next Steps:**
- Manually visit dryiceapp.com
- Check for "API", "Developers", or "Data Access" sections
- If API exists, verify it's free and accessible

### Sources
- [DryICE Website](https://dryiceapp.com/)
- [Fox 13 Seattle Article](https://www.fox13seattle.com/news/new-tool-tracks-ice-agents)

---

## 4. ICE in My Area ⚠️ REQUIRES VERIFICATION

### Overview
- **URL:** https://www.iceinmyarea.org/
- **Purpose:** Anonymous community reporting + location-based alerts
- **Features:** Community Safety Alert System, legal aid resources
- **Focus:** "Presence, not activity" tracking

### Technical Details
- **Status:** ⚠️ Website active (iceinmyarea.org/en)
- **API:** Not found in search results
- **Privacy:** Anonymous reporting emphasized
- **Resources:** Links to legal aid and community support

### Feasibility Assessment
**⚠️ REQUIRES VERIFICATION**

**Action Required:**
1. Visit iceinmyarea.org directly
2. Check for API documentation
3. Contact site administrators about data access
4. Evaluate data quality and verification process

**Estimated Research Time:** 1-2 hours

**Next Steps:**
- Explore iceinmyarea.org/en/resources for API info
- Look for developer documentation
- Contact via contact form or email

### Sources
- [ICE in My Area Website](https://www.iceinmyarea.org/en)
- [Fox 13 Seattle - Tracking Tool](https://www.fox13seattle.com/news/new-tool-tracks-ice-agents)
- [ICE in My Area Resources](https://www.iceinmyarea.org/en/resources)

---

## Reddit Subreddits ✅ IMMEDIATE ACTION

### New Subreddits Added
Already implemented in `reddit_scraper.py`:

1. **r/nj_politics** ✅
   - Added to SUBREDDITS dict
   - Default ZIP: 07060 (Plainfield)
   - Coverage: All 4 cities

**Action Required:** None - already integrated!

### Additional Subreddits to Consider

2. **r/Newark** (if active)
   - Newark is near Plainfield, Hoboken
   - ZIP: 07102
   - May have relevant discussions

3. **r/JerseyCity** (if not already included)
   - Near Hoboken
   - ZIP: 07302
   - Active community

4. **r/immigration** (national subreddit)
   - National discussions
   - May mention NJ cities
   - Higher signal volume

**Effort:** 5 minutes to add each subreddit
**Cost:** $0 (Reddit API already configured)
**Expected Signals:** +10-20/week per active subreddit

---

## Recommendations

### Immediate Actions (This Week)

1. ✅ **Reddit r/nj_politics** - Already added! Test it:
   ```powershell
   cd c:\Programming\heat
   .\.venv\Scripts\python.exe processing\reddit_scraper.py
   ```

2. ✅ **Add more Reddit subreddits** - Low effort, high value:
   - r/Newark
   - r/JerseyCity
   - r/immigration

### Short-Term Research (Next 2 Weeks)

3. ⚠️ **Verify DryICE and ICE in My Area**
   - Manually visit websites
   - Check for API documentation
   - Contact developers if needed
   - **Time:** 2-4 hours total

4. ✅ **Investigate RedadAlertas API**
   - Review GitHub source code for API endpoints
   - Contact Cosecha organization for research access
   - Create scraper if API is accessible
   - **Time:** 6-10 hours
   - **Priority:** High (best quality data)

### Not Recommended

5. ❌ **ICEBlock** - Do not pursue
   - Removed from App Store
   - No public API
   - Legal/ethical concerns
   - Ephemeral data (4-hour retention)

---

## Legal & Ethical Considerations

### Acceptable Use
✅ **Use for:**
- Civic safety awareness
- Research purposes
- Aggregated trend analysis
- Community protection

❌ **Do NOT use for:**
- Individual targeting or tracking
- Real-time operational enforcement
- Disclosure of individual identities
- Any purpose that harms individuals

### Data Privacy Requirements
1. **Anonymization:** Never store or display individual identifiers
2. **Aggregation:** Only show trends, not individual reports
3. **Buffer Delays:** Maintain 24-hour delay (already implemented)
4. **Source Attribution:** Credit community trackers appropriately
5. **Opt-Out:** Respect any data removal requests

### License Compliance
- **RedadAlertas (AGPL-3.0):** Requires attribution + sharing modifications
- **Research Use:** Generally permitted under fair use + civic purposes
- **Contact Organizations:** When in doubt, ask for permission

---

## Implementation Priority

### Tier 1: Immediate (Already Done) ✅
- [x] Add r/nj_politics to Reddit scraper
- **Status:** Complete
- **Cost:** $0
- **Expected Signals:** +5-10/week

### Tier 2: Quick Wins (This Week) ✅
- [ ] Add r/Newark, r/JerseyCity, r/immigration to Reddit scraper
- **Effort:** 15 minutes
- **Cost:** $0
- **Expected Signals:** +15-30/week

### Tier 3: Moderate Effort (Next 2 Weeks) ⚠️
- [ ] Research DryICE API availability
- [ ] Research ICE in My Area API availability
- [ ] Contact developers if APIs exist
- **Effort:** 2-4 hours research
- **Cost:** $0 (if APIs are free)
- **Expected Signals:** 10-30/week (if successful)

### Tier 4: High Value, Higher Effort (Next Month) ✅
- [ ] Investigate RedadAlertas API via GitHub source code
- [ ] Contact Cosecha for research access
- [ ] Build redadalertas_scraper.py
- **Effort:** 6-10 hours
- **Cost:** $0
- **Expected Signals:** 10-30/week (verified, high-quality data)
- **Priority:** High

---

## Cost Summary

| Source | Status | Cost | Implementation Time | Expected Signals/Week |
|--------|--------|------|---------------------|----------------------|
| r/nj_politics | ✅ Done | $0 | 0 min (complete) | 5-10 |
| r/Newark, r/JerseyCity, r/immigration | 🔜 To add | $0 | 15 min | 15-30 |
| RedadAlertas API | 🔜 Research needed | $0 | 6-10 hours | 10-30 (verified) |
| DryICE API | ⚠️ Verify | Unknown | 2-4 hours | 10-30 (if available) |
| ICE in My Area API | ⚠️ Verify | Unknown | 2-4 hours | 10-30 (if available) |
| ICEBlock | ❌ Not viable | N/A | N/A | N/A |

**Total Potential Addition:** 50-130 signals/week (if all sources work out)
**Total Cost:** $0 (all free/open source)
**Total Effort:** 8-20 hours over 4 weeks

---

## Next Steps

### Action Plan

**Today (5 minutes):**
1. Test r/nj_politics in Reddit scraper:
   ```powershell
   cd c:\Programming\heat
   .\.venv\Scripts\python.exe processing\reddit_scraper.py
   ```

**This Week (30 minutes):**
2. Add r/Newark, r/JerseyCity, r/immigration to reddit_scraper.py
3. Test expanded Reddit coverage

**Next 2 Weeks (6-10 hours):**
4. Deep dive into RedadAlertas GitHub repositories
5. Extract API endpoints from source code
6. Contact Cosecha for research access if needed
7. Build redadalertas_scraper.py

**Optional (2-4 hours):**
8. Manually verify DryICE and ICE in My Area for APIs
9. Contact developers if APIs exist

**Not Recommended:**
10. ❌ Skip ICEBlock (removed from App Store, no API)

---

## Conclusion

**Immediate Win:** r/nj_politics added to Reddit scraper (already done!)

**Quick Additions:** More Reddit subreddits (15 min, +15-30 signals/week)

**High-Value Investment:** RedadAlertas API integration (6-10 hours, +10-30 verified signals/week)

**Total Addition Potential:** 30-70 signals/week from community trackers

**Everything Remains Free:** $0/month, all open source or free APIs ✅
