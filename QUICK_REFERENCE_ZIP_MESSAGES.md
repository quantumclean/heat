# ZIP Code User Messages - Quick Reference

## All Possible ZIP Code Messages

### 1. Invalid Format ❌
**Triggers:** Not 5 digits, contains letters, empty
```
⚠️ Please enter a valid 5-digit ZIP code.
```
**Examples:** "123", "ABCDE", "", "1234", "123456"

---

### 2. Out of State 🌎
**Triggers:** Valid 5-digit ZIP but outside NJ range (07001-08989)
```
📍 ZIP [code] is outside New Jersey.

This tool currently covers New Jersey only. New Jersey ZIP codes 
range from 07001-08989.
```
**Examples:**
- 90210 → Los Angeles, CA
- 10001 → New York, NY
- 02134 → Boston, MA
- 33139 → Miami, FL

---

### 3. Valid NJ ZIP - No Data ✅
**Triggers:** ZIP in range 07001-08989, but no clusters/news in past 14 days
```
✅ No ICE activity signals in ZIP [code] for the past 14 days.

This is a valid New Jersey ZIP code. No activity reports have 
been recorded in this area recently.

⚠️ This does not guarantee safety. Data may be delayed or 
incomplete. Always verify independently and stay informed through 
community resources.
```
**Examples:**
- **08859** → Sayreville, NJ (THE FIX!)
- 08873 → Somerset, NJ
- 07950 → Morris Plains, NJ
- Any NJ ZIP without recent activity

---

### 4. Valid NJ ZIP - Has Data ⚠️
**Triggers:** ZIP in range 07001-08989, with clusters/news in past 14 days
```
⚠️ [count] signal(s) found in ZIP [code] (past 14 days)

[List of signals with dates, sources, and summaries]

This is interpretive data. Verify independently and consult 
community resources.
```
**Examples:**
- 07060 → Plainfield, NJ (if has data)
- 08817 → Edison, NJ (if has data)
- Any ZIP with active reports

---

## Search Behavior

### Searching in the Search Bar

#### For ZIPs in ZIP_BOUNDARIES (has detailed coordinates):
```
📍 ZIP 07060
```
- Clicking → Flies to ZIP on map (zoom 15)

#### For valid 5-digit ZIPs not in boundaries:
```
📍 ZIP 08859 (NJ)          ← If New Jersey
📍 ZIP 90210 (Out of state) ← If not New Jersey
```
- Clicking NJ ZIP → Opens "Am I Safe?" panel, runs check
- Clicking out-of-state → Alert: "This tool covers NJ only"

#### For streets:
```
🛣️ Front Street
```
- Clicking → Flies to street coordinates (zoom 16)

#### For clusters:
```
🔥 Cluster #123: ICE activity reported near...
```
- Clicking → Flies to cluster, highlights card

---

## Testing the Fixes

### Test 1: The Original Issue ✅
1. Search "08859" or use "Am I Safe?" with 08859
2. **Expected:** Clear message that it's valid NJ ZIP with no data
3. **Previously:** Unclear "No results" or just "No signals"

### Test 2: Multiple ZIPs
Try each of these and verify the correct message:

| ZIP   | City              | Expected Result                    |
|-------|-------------------|------------------------------------|
| 08859 | Sayreville, NJ    | ✅ Valid NJ - No data             |
| 07060 | Plainfield, NJ    | ✅ Valid NJ - Check for data      |
| 90210 | Los Angeles, CA   | 🌎 Out of state                   |
| 10001 | New York, NY      | 🌎 Out of state                   |
| 12345 | Schenectady, NY   | 🌎 Out of state                   |
| 123   | -                 | ❌ Invalid format                 |
| ABCDE | -                 | ❌ Invalid format                 |
| 07001 | Avenel, NJ        | ✅ Valid NJ (edge: lowest)        |
| 08989 | Zarephath, NJ     | ✅ Valid NJ (edge: highest)       |
| 07000 | -                 | 🌎 Out of state (below NJ)        |
| 08990 | -                 | 🌎 Out of state (above NJ)        |

### Test 3: Search Dropdown
1. Type "088" in search bar
2. **Expected:** Shows any matching ZIPs from boundaries + "08859 (NJ)" if typed fully
3. Type "08859" fully
4. **Expected:** Shows "ZIP 08859 (NJ)" in results

### Test 4: "Am I Safe?" Feature
1. Click "🛡️ Am I Safe?" button
2. Try each test ZIP from table above
3. **Expected:** Appropriate message for each

---

## Edge Cases Handled

✅ **Leading zeros:** "8859" → Padded to "08859"
✅ **Mixed input:** Trimmed and validated
✅ **Empty input:** Clear error message
✅ **Letters:** Clear error message
✅ **Wrong length:** Clear error message
✅ **Boundary values:** 07001, 08989 work; 07000, 08990 don't
✅ **No coordinates:** Opens "Am I Safe?" instead of failing
✅ **No data:** Clear "valid but no data" message

---

## Quick Developer Reference

### NJ ZIP Range:
```javascript
const isNJ = (zipNum >= 7001 && zipNum <= 8989);
```

### Validation Function:
```javascript
function isNewJerseyZip(zip) {
    const zipNum = parseInt(zip, 10);
    return (zipNum >= 7001 && zipNum <= 8989);
}
```

### Format Check:
```javascript
if (!/^\d{5}$/.test(zip)) {
    // Invalid format
}
```

### Message Priority:
1. Format validation (must be 5 digits)
2. State validation (must be NJ)
3. Data availability (check clusters/news)
4. Display appropriate message

---

## Success Metrics

✅ **08859 now works** - Main goal achieved!
✅ **All NJ ZIPs recognized** - Not limited to predefined list
✅ **Clear messages** - Users understand what's happening
✅ **Graceful fallbacks** - No broken states or confusing errors
✅ **Better UX** - Informative, helpful, and actionable feedback

---

## URLs to Test

- **Validation Test Suite:** http://localhost:8000/test_zip_validation.html
- **Main Application:** http://localhost:8000/index.html
- **Data Export:** http://localhost:8000/data-export.html
