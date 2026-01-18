# HEAT Ethical Use License v1.0

## Preamble

This license governs the use, modification, and distribution of HEAT (Heatmap of Elevated Attention Tracking) and derivative works. It is designed to keep the software freely available while **preventing modification into surveillance technology**.

The core innovation of HEAT is its **inversion of surveillance optimization**—intentional delays, resolution limits, and identity exclusion that make privacy preservation architectural rather than policy-based. This license ensures those properties are preserved in all derivative works.

---

## Terms and Conditions

### 1. Definitions

**"Software"** means the HEAT source code, documentation, and associated files.

**"Derivative Work"** means any work based on the Software, including modifications, translations, adaptations, or works that incorporate substantial portions of the Software.

**"Core Constraints"** means the ethical design requirements specified in Section 3.

**"Covered Work"** means either the unmodified Software or a Derivative Work.

### 2. Grant of Rights

Subject to the terms of this license, you are granted a perpetual, worldwide, non-exclusive, royalty-free license to:

a) Use the Software for any purpose  
b) Study how the Software works  
c) Modify the Software  
d) Distribute the Software and Derivative Works  

### 3. Core Constraints (Mandatory)

**Any Covered Work MUST maintain the following constraints. Violation of any constraint terminates your license rights.**

#### 3.1 Temporal Buffer Requirement

All public-facing outputs must enforce a minimum delay:

```
MINIMUM_DELAY ≥ 24 hours
```

- No real-time or near-real-time civic monitoring outputs
- No alerts, notifications, or displays based on data less than 24 hours old
- Internal processing may use fresher data, but public visibility requires delay

#### 3.2 Spatial Resolution Ceiling

Maximum geographic resolution for any output:

```
MAXIMUM_RESOLUTION = ZIP code level (5-digit US) or equivalent
```

- No address-level, coordinate-level, or venue-level outputs
- No "heatmaps" with resolution finer than ZIP centroids
- No reverse-geocoding to enhance resolution

#### 3.3 Source Corroboration Requirement

All visible outputs must meet corroboration thresholds:

```
MINIMUM_SOURCES ≥ 2 distinct sources
MINIMUM_CLUSTER_SIZE ≥ 3 signals
```

- No single-source claims visible to users
- No outputs based on individual reports without corroboration

#### 3.4 Identity Exclusion Architecture

The data model must architecturally exclude individual identifiers:

```
PROHIBITED_FIELDS = [
    user_id, device_id, ip_address, phone_number,
    name, email, social_media_handle, biometric_data,
    precise_coordinates, street_address, license_plate
]
```

- These fields must not exist in the schema (not merely be empty)
- No mechanism to link signals to individuals may be added
- Anonymous submission must remain anonymous through the pipeline

#### 3.5 Uncertainty Disclosure

All outputs must include uncertainty quantification:

- Confidence scores or intervals
- Data quality indicators  
- Explicit "this is not a verified claim" disclaimers
- Silence context ("no data ≠ safe")

### 4. Prohibited Uses

The following uses are expressly prohibited and terminate license rights:

a) **Real-time alerting** - Any system providing alerts based on data less than 24 hours old

b) **Location tracking** - Using the Software to track movements of individuals or groups

c) **Predictive enforcement** - Using outputs to predict or direct law enforcement activity

d) **Identity resolution** - Attempting to identify individuals from aggregated data

e) **Resolution enhancement** - Modifying the system to provide finer spatial resolution

f) **Delay reduction** - Modifying the system to reduce temporal buffers below 24 hours

g) **Surveillance integration** - Integrating with real-time surveillance systems, facial recognition, license plate readers, or similar technologies

h) **Commercial surveillance** - Selling or licensing data or insights for surveillance purposes

### 5. Attribution

Derivative Works must:

a) Include prominent notice that the work is based on HEAT  
b) Include a copy of this license  
c) Clearly state any modifications made  
d) Not imply endorsement by HEAT contributors without permission

### 6. Copyleft for Core Constraints

If you distribute a Derivative Work, it must:

a) Be licensed under this license or a compatible license with equivalent Core Constraints  
b) Make source code available under the same terms  
c) Include documentation of how Core Constraints are maintained

### 7. Verification

Derivative Works should include automated verification:

```python
def verify_ethical_compliance():
    assert MINIMUM_DELAY_HOURS >= 24
    assert MAXIMUM_RESOLUTION == "ZIP"
    assert MINIMUM_SOURCES >= 2
    assert not schema_contains_identity_fields()
    assert outputs_include_uncertainty()
```

### 8. Termination

Your rights under this license terminate automatically if you:

a) Violate any Core Constraint  
b) Use the Software for any Prohibited Use  
c) Fail to comply with attribution requirements

Upon termination, you must cease all use and distribution of Covered Works.

### 9. Warranty Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

### 10. Limitation of Liability

IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### 11. Community Enforcement

The HEAT community may:

a) Publicly identify non-compliant derivatives  
b) Request removal of non-compliant works from distribution platforms  
c) Pursue legal remedies for license violations

### 12. Interpretation

If any provision of this license is held unenforceable, the remaining provisions continue in effect. The Core Constraints represent the essential purpose of this license and may not be waived.

---

## Rationale

This license exists because **architecture is ethics**. A system designed for 24-hour delays cannot be trivially converted to real-time surveillance. A system that cannot store addresses cannot leak them. A system requiring multi-source corroboration cannot amplify single-actor disinformation.

These constraints are not limitations—they are the innovation. By encoding ethics into architecture and architecture into license, we create technology that serves communities rather than surveilling them.

---

## Quick Reference

| Requirement | Minimum | Maximum |
|-------------|---------|---------|
| Temporal delay | 24 hours | — |
| Spatial resolution | — | ZIP code |
| Source corroboration | 2 sources | — |
| Cluster size | 3 signals | — |
| Identity fields | 0 | 0 |

---

## Contact

For questions about this license or to report violations:
- Repository: https://github.com/quantumclean/heat
- Issues: https://github.com/quantumclean/heat/issues

---

*HEAT Ethical Use License v1.0*  
*Effective Date: January 17, 2026*
