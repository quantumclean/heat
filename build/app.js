/**
 * HEAT — They Are Here | Community Awareness Map
 * Static frontend for aggregated public attention patterns
 * 
 * Cultural regions are emergent coordination systems whose boundaries
 * appear where shared behavior fails — not where maps say they should.
 */

// Default to statewide NJ view — show all active reports
const DEFAULT_CENTER = [40.0583, -74.4057];  // NJ state center
const DEFAULT_ZOOM = 8;  // Show all of NJ

// Plainfield center for fallback positioning
const PLAINFIELD_CENTER = [40.6137, -74.4154];

// ZIP code enhanced boundaries for precise positioning
const ZIP_BOUNDARIES = {
    "07060": {
        center: [40.6137, -74.4154],
        bounds: { n: 40.6250, s: 40.6020, e: -74.4000, w: -74.4350 }
    },
    "07062": {
        center: [40.6280, -74.4050],
        bounds: { n: 40.6400, s: 40.6160, e: -74.3900, w: -74.4200 }
    },
    "07063": {
        center: [40.5980, -74.4280],
        bounds: { n: 40.6100, s: 40.5860, e: -74.4100, w: -74.4450 }
    },
    // Edison, NJ (approximate bounds for placement)
    "08817": {
        center: [40.5300, -74.3930],
        bounds: { n: 40.5480, s: 40.5120, e: -74.3600, w: -74.4300 }
    },
    "08820": {
        center: [40.5800, -74.3600],
        bounds: { n: 40.5950, s: 40.5650, e: -74.3300, w: -74.3900 }
    },
    "08837": {
        center: [40.5290, -74.3370],
        bounds: { n: 40.5450, s: 40.5150, e: -74.3100, w: -74.3650 }
    }
};

// Major street coordinates for precise cluster placement
const STREET_COORDS = {
    "front street": { lat: 40.6145, lng: -74.4185, zip: "07060" },
    "park avenue": { lat: 40.6180, lng: -74.4120, zip: "07060" },
    "watchung avenue": { lat: 40.6200, lng: -74.4080, zip: "07060" },
    "south avenue": { lat: 40.6050, lng: -74.4180, zip: "07060" },
    "plainfield avenue": { lat: 40.6160, lng: -74.4200, zip: "07060" },
    "west front street": { lat: 40.6140, lng: -74.4230, zip: "07060" },
    "east front street": { lat: 40.6148, lng: -74.4100, zip: "07060" },
    "somerset street": { lat: 40.6195, lng: -74.4145, zip: "07062" },
    "green brook road": { lat: 40.6280, lng: -74.4050, zip: "07062" },
    "grove street": { lat: 40.6240, lng: -74.4080, zip: "07062" },
    "leland avenue": { lat: 40.6050, lng: -74.4250, zip: "07063" },
    "woodland avenue": { lat: 40.5990, lng: -74.4300, zip: "07063" },
    "clinton avenue": { lat: 40.6020, lng: -74.4220, zip: "07063" },
    "terrill road": { lat: 40.5960, lng: -74.4320, zip: "07063" },
    "west 7th street": { lat: 40.6180, lng: -74.4200, zip: "07060" },
    "west 4th street": { lat: 40.6155, lng: -74.4180, zip: "07060" },
    "2nd street": { lat: 40.6135, lng: -74.4150, zip: "07060" },
    "3rd street": { lat: 40.6145, lng: -74.4160, zip: "07060" },
    "central avenue": { lat: 40.6170, lng: -74.4130, zip: "07060" },
    "madison avenue": { lat: 40.6100, lng: -74.4140, zip: "07060" },
    // Edison POIs / streets (approximate)
    "vineyard road": { lat: 40.5400, lng: -74.3770, zip: "08817" },
    "route 1": { lat: 40.5350, lng: -74.4050, zip: "08817" },
    "old post road": { lat: 40.5550, lng: -74.3700, zip: "08820" },
    "raritan center": { lat: 40.5260, lng: -74.3370, zip: "08837" }
};

// Legacy ZIP_COORDS for backward compatibility
const ZIP_COORDS = {
    // Plainfield area
    "07060": [40.6137, -74.4154],
    "07062": [40.6280, -74.4050],
    "07063": [40.5980, -74.4280],
    // Central NJ
    "08817": [40.5187, -74.4121],  // Edison
    "08901": [40.4862, -74.4518],  // New Brunswick
    "08854": [40.5570, -74.4588],  // Piscataway
    "08840": [40.5432, -74.3629],  // Metuchen
    "08904": [40.4968, -74.4254],  // Highland Park
    "08812": [40.5887, -74.4718],  // Dunellen
    "08876": [40.5743, -74.6099],  // Somerville
    "08807": [40.5989, -74.6104],  // Bridgewater
    // North NJ
    "07102": [40.7357, -74.1724],  // Newark
    "07302": [40.7178, -74.0431],  // Jersey City
    "07030": [40.7439, -74.0324],  // Hoboken
    "07960": [40.7968, -74.4815],  // Morristown
    "07201": [40.6640, -74.2107],  // Elizabeth
    "07601": [40.8859, -74.0435],  // Hackensack
    // South NJ
    "08608": [40.2171, -74.7429],  // Trenton
    "08540": [40.3573, -74.6672],  // Princeton
    "08401": [39.3643, -74.4229],  // Atlantic City
    "08101": [39.9259, -75.1196],  // Camden
    // Edison
    "08817": [40.5300, -74.3930],
    "08820": [40.5800, -74.3600],
    "08837": [40.5290, -74.3370],
};

// ============================================
// Intelligent Cluster Positioning
// ============================================

/**
 * Get precise coordinates for a cluster based on text content
 * Looks for street mentions and distributes within ZIP bounds
 */
function getClusterCoordinates(cluster) {
    const zip = String(cluster.zip).padStart(5, '0');
    let zipData = ZIP_BOUNDARIES[zip];
    
    // First, try to use detailed ZIP_BOUNDARIES if available
    if (!zipData) {
        // Heuristic: if text indicates Edison and we have Edison bounds, use them
        const text = (cluster.summary || cluster.representative_text || '').toLowerCase();
        const mentionsEdison = text.includes("edison");
        const mentionsCostco = text.includes("costco") || text.includes("vineyard road");
        if (mentionsEdison) {
            const edisonZip = mentionsCostco ? "08817" : "08820"; // prefer 08817 for Costco
            if (ZIP_BOUNDARIES[edisonZip]) {
                zipData = ZIP_BOUNDARIES[edisonZip];
            }
        }
    }
    
    // If we have detailed boundary data, use intelligent positioning
    if (zipData) {
        const text = (cluster.summary || cluster.representative_text || '').toLowerCase();

        // Downtown Plainfield hinting
        if (text.includes("downtown plainfield") && ZIP_BOUNDARIES["07060"]) {
            const d = STREET_COORDS["front street"];
            const jitter = () => (Math.random() - 0.5) * 0.002;
            return [d.lat + jitter(), d.lng + jitter()];
        }
        
        // Check for specific street mentions
        for (const [street, streetData] of Object.entries(STREET_COORDS)) {
            if (text.includes(street) && streetData.zip === zip) {
                // Small jitter around street location
                const jitter = () => (Math.random() - 0.5) * 0.002;
                return [streetData.lat + jitter(), streetData.lng + jitter()];
            }
        }
        
        // No street match - distribute based on cluster ID within ZIP bounds
        const seed = cluster.id || Math.random() * 100;
        const bounds = zipData.bounds;
        
        // Create deterministic but varied position using cluster ID
        const latRange = bounds.n - bounds.s;
        const lngRange = bounds.e - bounds.w;
        
        // Use golden ratio for better distribution
        const phi = 1.618033988749895;
        const latOffset = ((seed * phi) % 1) * latRange * 0.6;
        const lngOffset = (((seed * phi * phi) % 1)) * lngRange * 0.6;
        
        // Position within 60% of bounds, centered
        const lat = bounds.s + latRange * 0.2 + latOffset;
        const lng = bounds.w + lngRange * 0.2 + lngOffset;
        
        return [lat, lng];
    }
    
    // Fallback: use ZIP_COORDS for broader NJ coverage
    if (ZIP_COORDS[zip]) {
        // Add small jitter so multiple clusters in same ZIP don't overlap exactly
        const baseCoords = ZIP_COORDS[zip];
        const seed = cluster.id || Math.random() * 100;
        const phi = 1.618033988749895;
        const jitterLat = ((seed * phi) % 1 - 0.5) * 0.01;  // ~1km jitter
        const jitterLng = ((seed * phi * phi) % 1 - 0.5) * 0.01;
        return [baseCoords[0] + jitterLat, baseCoords[1] + jitterLng];
    }
    
    // Final fallback: Plainfield center
    console.warn(`No coordinates found for ZIP ${zip}, using Plainfield center`);
    return PLAINFIELD_CENTER;
}

// ZIP to region mapping for filtering
// ============================================
// Behavioral Clustering System
// ============================================
// Cultural regions are emergent coordination systems whose boundaries
// appear where shared behavior fails — not where maps say they should.

/**
 * Calculate behavioral coordination metrics for a cluster
 * These metrics define HOW communities coordinate under pressure, not WHO they are
 */
function calculateCoordinationMetrics(cluster) {
    const signals = cluster.signals || [];
    const keywords = cluster.keywords || [];
    const zip = String(cluster.zip).padStart(5, '0');
    const coords = ZIP_COORDS[zip] || PLAINFIELD_CENTER;
    
    // METRIC 1: Signal Velocity (time tolerance)
    // How fast does information propagate? High velocity = tight coordination
    const timestamps = signals.map(s => new Date(s.date || s.timestamp).getTime()).sort();
    let velocityScore = 0;
    if (timestamps.length >= 2) {
        const timeDeltas = [];
        for (let i = 1; i < timestamps.length; i++) {
            timeDeltas.push((timestamps[i] - timestamps[i-1]) / 3600000);  // Hours
        }
        const avgDelta = timeDeltas.reduce((a,b) => a+b, 0) / timeDeltas.length;
        // Lower delta = higher velocity (faster coordination)
        velocityScore = Math.max(0, 100 - avgDelta);  // 0-100 scale
    }
    
    // METRIC 2: Density Comfort (urban/suburban/rural coordination mode)
    // Based on signal concentration and geographic spread
    const signalDensity = signals.length / Math.max(1, new Date() - new Date(cluster.first_date || cluster.date)) * 86400000;  // Signals per day
    const densityScore = Math.min(signalDensity * 20, 100);  // 0-100 scale
    
    // METRIC 3: Rule Negotiation Style (enforcement variance)
    // Measured by keyword diversity and source diversity
    const sourceTypes = new Set(signals.map(s => s.source_type || 'unknown'));
    const keywordVariance = keywords.length / Math.max(signals.length, 1);
    const negotiationScore = (sourceTypes.size * 20) + (keywordVariance * 30);  // 0-100 scale
    
    // METRIC 4: Movement Friction (transit connectivity proxy)
    // Inferred from geographic isolation and signal reach
    // Clusters near transit hubs have lower friction
    const nearTransitHub = ['07102', '07030', '07302', '08901'].includes(zip);  // Newark, Hoboken, Jersey City, New Brunswick
    const movementScore = nearTransitHub ? 80 : 40;  // 0-100 scale
    
    return {
        velocity: velocityScore,
        density: densityScore,
        negotiation: negotiationScore,
        movement: movementScore,
        composite: (velocityScore + densityScore + negotiationScore + movementScore) / 4
    };
}

/**
 * Discover emergent behavioral regions using hierarchical clustering
 * Returns array of region objects with behavioral profiles
 */
function discoverBehavioralRegions(clusters) {
    if (!clusters || clusters.length === 0) return [];
    
    // Calculate metrics for each cluster
    const clusterMetrics = clusters.map(cluster => ({
        cluster: cluster,
        metrics: calculateCoordinationMetrics(cluster)
    }));
    
    // Simple hierarchical clustering based on behavioral similarity
    // Group clusters whose coordination protocols are similar
    const regions = [];
    const assigned = new Set();
    const threshold = 25;  // Behavioral similarity threshold
    
    clusterMetrics.forEach((item, idx) => {
        if (assigned.has(idx)) return;
        
        // Start new region with this cluster as seed
        const region = {
            clusters: [item.cluster],
            metrics: {...item.metrics},
            profile: null  // Will be assigned based on dominant metrics
        };
        
        assigned.add(idx);
        
        // Find similar clusters
        clusterMetrics.forEach((other, otherIdx) => {
            if (assigned.has(otherIdx)) return;
            
            // Calculate behavioral distance
            const distance = Math.sqrt(
                Math.pow(item.metrics.velocity - other.metrics.velocity, 2) +
                Math.pow(item.metrics.density - other.metrics.density, 2) +
                Math.pow(item.metrics.negotiation - other.metrics.negotiation, 2) +
                Math.pow(item.metrics.movement - other.metrics.movement, 2)
            );
            
            if (distance < threshold) {
                region.clusters.push(other.cluster);
                assigned.add(otherIdx);
                
                // Update region metrics (average)
                region.metrics.velocity = (region.metrics.velocity + other.metrics.velocity) / 2;
                region.metrics.density = (region.metrics.density + other.metrics.density) / 2;
                region.metrics.negotiation = (region.metrics.negotiation + other.metrics.negotiation) / 2;
                region.metrics.movement = (region.metrics.movement + other.metrics.movement) / 2;
                region.metrics.composite = (region.metrics.velocity + region.metrics.density + region.metrics.negotiation + region.metrics.movement) / 4;
            }
        });
        
        // Assign behavioral profile name based on dominant characteristics
        region.profile = assignBehavioralProfile(region.metrics);
        regions.push(region);
    });
    
    // Sort regions by cluster count (largest first)
    return regions.sort((a, b) => b.clusters.length - a.clusters.length);
}

/**
 * Assign human-readable behavioral profile based on coordination metrics
 * NOT geographic labels — these describe HOW communities coordinate
 */
function assignBehavioralProfile(metrics) {
    // High velocity + high density = "High-Velocity Urban"
    if (metrics.velocity > 60 && metrics.density > 60) {
        return "High-Velocity Urban";
    }
    
    // High movement + high negotiation = "Transit-Connected Hybrid"
    if (metrics.movement > 60 && metrics.negotiation > 60) {
        return "Transit-Connected Hybrid";
    }
    
    // Low velocity + low density = "Enforcement-Sparse Rural"
    if (metrics.velocity < 40 && metrics.density < 40) {
        return "Enforcement-Sparse Rural";
    }
    
    // High density + low movement = "Transit-Isolated Suburban"
    if (metrics.density > 50 && metrics.movement < 50) {
        return "Transit-Isolated Suburban";
    }
    
    // Medium everything = "Coordination Mediator"
    if (Math.abs(metrics.velocity - 50) < 20 && Math.abs(metrics.density - 50) < 20) {
        return "Coordination Mediator";
    }
    
    // High negotiation + variable others = "Multi-Modal Interface"
    if (metrics.negotiation > 70) {
        return "Multi-Modal Interface";
    }
    
    // Default fallback
    return "Mixed Coordination";
}

// Globals
let map;
let clustersData = null;
let timelineData = null;
let keywordsData = null;
let latestNewsData = null;
let alertsData = null;
let entropyData = null;
let is3DMode = false;
let clusterMarkers = [];
let currentLanguage = 'en';
let currentRegion = 'statewide';  // Track selected region for keyword filtering
let analyticsInitialized = false;
let analyticsBasePayload = { clusters: [] };
let analyticsQueuedClusters = null;
let analyticsRenderPending = false;

function getBaseUrl() {
    // Always use relative paths — works on GitHub Pages, localhost,
    // CloudFront, or any static host without hardcoded URLs.
    return './';
}

function snapshotAnalyticsBaseData() {
    if (!clustersData || !Array.isArray(clustersData.clusters)) {
        analyticsBasePayload = { clusters: [] };
        return;
    }
    analyticsBasePayload = Object.assign({}, clustersData, {
        clusters: clustersData.clusters.slice()
    });
}

function getAnalyticsBaseClusters() {
    return Array.isArray(analyticsBasePayload.clusters)
        ? analyticsBasePayload.clusters.slice()
        : [];
}

function scheduleAnalyticsRender(filteredClusters) {
    analyticsQueuedClusters = Array.isArray(filteredClusters) ? filteredClusters.slice() : [];
    if (analyticsRenderPending) return;

    analyticsRenderPending = true;
    requestAnimationFrame(() => {
        analyticsRenderPending = false;
        if (!analyticsBasePayload || !Array.isArray(analyticsBasePayload.clusters)) {
            snapshotAnalyticsBaseData();
        }

        clustersData = Object.assign({}, analyticsBasePayload || {}, {
            clusters: analyticsQueuedClusters ? analyticsQueuedClusters.slice() : []
        });

        try { renderMap(); } catch (e) { console.error('Analytics renderMap failed:', e); }
        try { renderClusters(); } catch (e) { console.error('Analytics renderClusters failed:', e); }
        try { updateDashboard(); } catch (e) { console.error('Analytics updateDashboard failed:', e); }
        try { updateQuickStats(); } catch (e) { console.error('Analytics updateQuickStats failed:', e); }
        try { renderSidebar(); } catch (e) { console.error('Analytics renderSidebar failed:', e); }
        try { wireSidebarToMap(); } catch (e) { console.error('Analytics wireSidebarToMap failed:', e); }
        
        // Additional analytics-specific updates
        try { 
            if (typeof updateDashboardWithFiltered === 'function') {
                updateDashboardWithFiltered(analyticsQueuedClusters);
            }
        } catch (e) { 
            console.error('Analytics updateDashboardWithFiltered failed:', e); 
        }
    });
}

function initAnalyticsIntegration() {
    const engine = window.filterEngine;
    const panel = window.analyticsPanel;

    if (!engine || !panel || typeof panel.init !== 'function' || typeof engine.initialize !== 'function') {
        console.info('Analytics modules unavailable; skipping analytics initialization');
        return;
    }

    if (!analyticsBasePayload || !Array.isArray(analyticsBasePayload.clusters) || analyticsBasePayload.clusters.length === 0) {
        snapshotAnalyticsBaseData();
    }

    if (!analyticsInitialized) {
        panel.init();
        panel.setFilterChangeHandler((filteredClusters) => {
            scheduleAnalyticsRender(filteredClusters);
        });
        analyticsInitialized = true;
    }

    panel.setDataContext({
        timeline: timelineData,
        keywords: keywordsData,
        latestNews: latestNewsData,
        alerts: alertsData
    });

    engine.initialize(getAnalyticsBaseClusters(), { keepFilters: analyticsInitialized });
    panel.refresh();
}

// ============================================
// i18n Translations
// ============================================

const TRANSLATIONS = {
    en: {
        title: "HEAT — They Are Here | Community Awareness Map",
        subtitle: "ICE-Related Community Reports — New Jersey",
        searchPlaceholder: "Search ZIP, street, or topic...",
        activeClusters: "Report Groups",
        trend: "Trend",
        keywords: "Keywords", 
        intensity: "Report Level",
        timeline: "Timeline",
        clusters: "Report Groups",
        resources: "Resources",
        about: "About",
        knowYourRights: "Know Your Rights",
        emergency: "Emergency Resources",
        submitInfo: "Submit Info",
        noResults: "No results found",
        tryAgain: "Try a different search",
        zipCode: "ZIP Code",
        street: "Street",
        cluster: "Cluster",
        signals: "signals",
        high: "High",
        medium: "Medium", 
        low: "Low",
        active: "Active",
        recent: "Recent",
        past: "Past",
        lastUpdated: "Last updated",
        noClusters: "No ICE-related report groups at this time.",
        interpretationNote: "This map shows aggregated ICE-related discussion patterns, not real-time events.",
        trustNote: "No tracking • ZIP-only precision • Shortest safe delay • No identities stored"
    },
    es: {
        title: "HEAT — They Are Here | Mapa de reportes comunitarios ICE",
        subtitle: "Reportes comunitarios sobre ICE — Nueva Jersey",
        searchPlaceholder: "Buscar código postal, calle o tema...",
        activeClusters: "Grupos de Reportes",
        trend: "Tendencia",
        keywords: "Palabras Clave",
        intensity: "Nivel de Reportes",
        timeline: "Cronología",
        clusters: "Grupos de Reportes",
        resources: "Recursos",
        about: "Acerca de",
        knowYourRights: "Conozca Sus Derechos",
        emergency: "Recursos de Emergencia",
        submitInfo: "Enviar Información",
        noResults: "No se encontraron resultados",
        tryAgain: "Intente una búsqueda diferente",
        zipCode: "Código Postal",
        street: "Calle",
        cluster: "Grupo",
        signals: "señales",
        high: "Alto",
        medium: "Medio",
        low: "Bajo",
        active: "Activo",
        recent: "Reciente",
        past: "Pasado",
        lastUpdated: "Última actualización",
        noClusters: "No hay grupos de reportes sobre ICE en este momento.",
        interpretationNote: "Este mapa muestra patrones agregados de discusión sobre ICE, no eventos en tiempo real.",
        trustNote: "Sin rastreo • Precisión solo por ZIP • Demora segura mínima • Sin identidades almacenadas"
    }
};

function t(key) {
    return TRANSLATIONS[currentLanguage]?.[key] || TRANSLATIONS['en'][key] || key;
}

function setLanguage(lang) {
    currentLanguage = lang;
    localStorage.setItem('heat-language', lang);
    updateUILanguage();
}

function updateUILanguage() {
    // Update text elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.textContent = t(key);
    });
    
    // Update placeholder attributes
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        el.placeholder = t(key);
    });
    
    // Re-render clusters with new language
    if (clustersData) {
        renderClusters();
    }
}

// ============================================
// News Sidebar
// ============================================

function renderSidebar() {
    const articlesContainer = document.getElementById("sidebar-articles");
    const countEl = document.getElementById("sidebar-count");
    const newsListEl = document.getElementById("latest-news-list");
    if (!articlesContainer) return;

    // Gather items from latest news and cluster summaries
    const items = [];

    // Latest news items
    if (latestNewsData?.items) {
        latestNewsData.items.forEach(item => {
            items.push({
                type: "news",
                text: item.summary || item.text || "",
                source: item.source || "Unknown",
                date: item.timestamp || item.date,
                zip: item.zip,
                urls: item.urls || [],
            });
        });
    }

    // Cluster summaries (if not already in news)
    if (clustersData?.clusters) {
        clustersData.clusters.forEach(cluster => {
            items.push({
                type: "cluster",
                text: cluster.summary || cluster.representative_text || "",
                source: (Array.isArray(cluster.sources) ? cluster.sources.join(", ") : cluster.sources) || "Multiple",
                date: cluster.dateRange?.end || cluster.dateRange?.start,
                zip: cluster.zip,
                clusterId: cluster.id,
            });
        });
    }

    // Sort by date descending
    items.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

    // Update count
    if (countEl) {
        countEl.textContent = `${items.length} signal${items.length !== 1 ? "s" : ""}`;
    }

    // Render into the sidebar news list
    if (newsListEl) {
        if (items.length === 0) {
            newsListEl.innerHTML = '<div class="no-data">No signals yet.</div>';
            return;
        }

        newsListEl.innerHTML = items.slice(0, 30).map((item, idx) => {
            const timeAgo = item.date ? getRelativeTime(item.date) : "";
            const zipStr = item.zip ? String(item.zip).padStart(5, "0") : "";
            const typeIcon = item.type === "cluster" ? "📊" : "📰";
            const linkHtml = item.urls?.length
                ? `<a href="${escapeHtml(item.urls[0])}" target="_blank" rel="noopener" class="sidebar-link">Source</a>`
                : "";

            return `
                <div class="latest-news__item" data-sidebar-idx="${idx}" data-zip="${zipStr}" data-cluster-id="${item.clusterId || ""}">
                    <div class="latest-news__meta">
                        <span class="latest-news__time">${typeIcon} ${timeAgo}</span>
                        <span class="latest-news__source">${escapeHtml(item.source)}</span>
                    </div>
                    <div class="latest-news__summary">${escapeHtml(truncate(item.text, 160))}</div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.3rem;">
                        <small style="color:var(--text-muted);">${zipStr}</small>
                        ${linkHtml}
                    </div>
                </div>
            `;
        }).join("");

        // Wire sidebar article clicks → fly to map location
        newsListEl.querySelectorAll(".latest-news__item").forEach(el => {
            el.addEventListener("click", () => {
                const zip = el.dataset.zip;
                const coords = ZIP_COORDS[zip];
                if (coords && map) {
                    map.flyTo(coords, 13, { duration: 0.8 });
                }

                // Highlight this item
                newsListEl.querySelectorAll(".latest-news__item").forEach(e => e.classList.remove("sidebar-active"));
                el.classList.add("sidebar-active");
            });
        });
    }

    // Render source badges
    renderSourceBadges();
}

function renderSourceBadges() {
    const container = document.getElementById("sidebar-sources");
    if (!container) return;

    // Collect unique sources from data
    const sources = new Set();

    if (latestNewsData?.items) {
        latestNewsData.items.forEach(item => {
            if (item.source) sources.add(item.source);
        });
    }
    if (clustersData?.clusters) {
        clustersData.clusters.forEach(cluster => {
            if (Array.isArray(cluster.sources)) {
                cluster.sources.forEach(s => sources.add(s));
            } else if (cluster.sources) {
                sources.add(cluster.sources);
            }
        });
    }

    if (sources.size === 0) {
        container.innerHTML = "";
        return;
    }

    container.innerHTML = Array.from(sources).sort().map(src =>
        `<span class="source-badge active">${escapeHtml(src)}</span>`
    ).join("");
}

/**
 * Wire map cluster marker click → highlight sidebar article
 */
function wireSidebarToMap() {
    // When a cluster marker popup opens, highlight matching sidebar item
    if (!map) return;
    map.on("popupopen", (e) => {
        const popup = e.popup;
        const content = popup.getContent() || "";
        // Extract cluster ID from popup
        const match = content.match(/Cluster #(\d+)/);
        if (match) {
            const clusterId = match[1];
            const newsListEl = document.getElementById("latest-news-list");
            if (newsListEl) {
                newsListEl.querySelectorAll(".latest-news__item").forEach(el => {
                    el.classList.remove("sidebar-active");
                    if (el.dataset.clusterId === clusterId) {
                        el.classList.add("sidebar-active");
                        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    }
                });
            }
        }
    });
}

// ============================================
// UX Enhancement Functions
// ============================================

/**
 * Show loading overlay while data loads
 * Pattern from Citizen app - gives users immediate feedback
 */
function showLoading(message = "Loading map data...") {
    const overlay = document.getElementById("loading-overlay");
    const text = overlay?.querySelector(".loading-text");
    if (overlay) {
        if (text) text.textContent = message;
        overlay.classList.remove("hidden");
        overlay.setAttribute("aria-busy", "true");
    }
}

/**
 * Hide loading overlay when data is ready
 */
function hideLoading() {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) {
        overlay.classList.add("hidden");
        overlay.setAttribute("aria-busy", "false");
    }
}

/**
 * Show error state with retry button
 * Pattern from 311 dashboards - graceful failure recovery
 */
function showError(message = "Something went wrong while loading the map.") {
    const errorState = document.getElementById("error-state");
    const errorMessage = document.getElementById("error-message");
    
    if (errorState && errorMessage) {
        errorMessage.textContent = message;
        errorState.classList.remove("hidden");
    }
    hideLoading();
}

/**
 * Hide error state
 */
function hideError() {
    const errorState = document.getElementById("error-state");
    if (errorState) {
        errorState.classList.add("hidden");
    }
}

/**
 * Reset map to default NJ view
 * Pattern from Nextdoor - helps users who get lost navigating
 */
function resetMapView() {
    if (!map) return;
    
    // Smooth fly animation back to default view
    map.flyTo(DEFAULT_CENTER, DEFAULT_ZOOM, {
        duration: 1.2,
        easeLinearity: 0.25
    });
    
    // Reset active region button
    document.querySelectorAll('.region-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.region === 'statewide');
    });
    
    // Show feedback to user
    const subtitle = document.querySelector('.subtitle');
    if (subtitle) {
        const originalText = subtitle.textContent;
        subtitle.textContent = "🎯 Showing all of New Jersey";
        setTimeout(() => {
            subtitle.textContent = originalText;
        }, 3000);
    }
    
    // Haptic feedback on mobile
    if (navigator.vibrate) {
        navigator.vibrate(10);
    }
}

/**
 * Initialize keyboard navigation
 * Pattern from accessibility best practices - keyboard users can navigate
 */
function initKeyboardNavigation() {
    // Escape key closes search results and modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Close search results
            const searchResults = document.getElementById('search-results');
            if (searchResults && !searchResults.classList.contains('hidden')) {
                searchResults.classList.add('hidden');
                document.getElementById('search-input')?.blur();
            }
            
            // Close safe check panel
            const safePanel = document.getElementById('safe-check-panel');
            if (safePanel && !safePanel.classList.contains('hidden')) {
                safePanel.classList.add('hidden');
            }
        }
        
        // Ctrl/Cmd + K focuses search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('search-input')?.focus();
        }
        
        // R key resets map view
        if (e.key === 'r' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT') {
            resetMapView();
        }
    });
    
    // Trap focus in modals when open
    // Improve keyboard navigation for region buttons
    const regionButtons = document.querySelectorAll('.region-btn');
    regionButtons.forEach((button, index) => {
        button.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                const next = regionButtons[index + 1] || regionButtons[0];
                next.focus();
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                const prev = regionButtons[index - 1] || regionButtons[regionButtons.length - 1];
                prev.focus();
            }
        });
    });
}

/**
 * Announce changes to screen readers
 * Pattern from WCAG 2.1 - assistive technology support
 */
function announceToScreenReader(message) {
    // Find or create live region
    let liveRegion = document.getElementById('sr-live-region');
    if (!liveRegion) {
        liveRegion = document.createElement('div');
        liveRegion.id = 'sr-live-region';
        liveRegion.className = 'sr-only';
        liveRegion.setAttribute('role', 'status');
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        document.body.appendChild(liveRegion);
    }
    
    // Clear and announce
    liveRegion.textContent = '';
    setTimeout(() => {
        liveRegion.textContent = message;
    }, 100);
}

/**
 * Enhanced empty state messaging
 * Pattern from Citizen - contextual help when no data
 */
function renderEmptyState(container, type = 'clusters') {
    const emptyMessages = {
        clusters: {
            icon: '🗺️',
            title: 'No Reports in View',
            message: 'Try zooming out or selecting a different region.',
            action: 'reset-map',
            actionText: 'View All New Jersey'
        },
        news: {
            icon: '📰',
            title: 'No Recent News',
            message: 'Check back soon for updates.',
            action: null,
            actionText: null
        },
        keywords: {
            icon: '🔍',
            title: 'No Keywords Yet',
            message: 'Keywords appear when multiple reports mention similar topics.',
            action: null,
            actionText: null
        }
    };
    
    const config = emptyMessages[type] || emptyMessages.clusters;
    
    const html = `
        <div class="no-data" role="status">
            <p><span style="font-size: 3rem;" aria-hidden="true">${config.icon}</span></p>
            <p>${config.title}</p>
            <small>${config.message}</small>
            ${config.action ? `<button id="${config.action}" class="glass-btn" style="margin-top: 1rem;">${config.actionText}</button>` : ''}
        </div>
    `;
    
    if (container) {
        container.innerHTML = html;
        
        // Wire up action button if present
        if (config.action) {
            const actionBtn = container.querySelector(`#${config.action}`);
            if (actionBtn && config.action === 'reset-map') {
                actionBtn.addEventListener('click', resetMapView);
            }
        }
    }
}

// ============================================
// Time to Midnight Clock Widget (Dynamic Behavioral Regions)
// ============================================

function computeMidnightScore(region) {
    /**
     * Compute a composite "midnight score" (0-100) for a behavioral region
     * Based on: signal volume, trend, burst score, active alerts, coordination metrics
     */
    if (!region.clusters || region.clusters.length === 0) return 0;
    
    const regionClusters = region.clusters;
    
    // Component 1: Recent signal volume (last 7 days)
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const recentSignals = regionClusters.filter(c => {
        const clusterDate = new Date(c.latest_date || c.date);
        return clusterDate >= sevenDaysAgo;
    });
    const volumeScore = Math.min((recentSignals.length / 10) * 40, 40);  // Max 40 points
    
    // Component 2: Trend magnitude (global, not per-region)
    const trend = timelineData?.trend || {};
    const trendMagnitude = Math.abs(trend.magnitude || 0);
    const trendDirection = trend.direction || 'stable';
    let trendScore = 0;
    if (trendDirection === 'increasing') {
        trendScore = Math.min((trendMagnitude / 50) * 30, 30);  // Max 30 points
    } else if (trendDirection === 'decreasing') {
        trendScore = Math.max(-(trendMagnitude / 50) * 15, -15);  // Can reduce score
    }
    
    // Component 3: Burst detection
    const recentBurst = (timelineData?.weeks || [])
        .slice(-4)  // Last 4 weeks
        .some(week => week.burst_score && week.burst_score > 0.5);
    const burstScore = recentBurst ? 15 : 0;  // Max 15 points
    
    // Component 4: Active alert level
    let alertScore = 0;
    if (alertsData && alertsData.cluster_alerts) {
        const clusterZIPs = new Set(regionClusters.map(c => String(c.zip).padStart(5, '0')));
        const regionAlerts = alertsData.cluster_alerts.filter(alert => {
            const zip = String(alert.zip).padStart(5, '0');
            return clusterZIPs.has(zip);
        });
        if (regionAlerts.length > 0) {
            const hasHighPriority = regionAlerts.some(a => a.priority === 'high' || a.tier >= 2);
            alertScore = hasHighPriority ? 15 : 10;  // Max 15 points
        }
    }
    
    // Component 5: Coordination velocity bonus (unique to behavioral approach)
    // High-velocity regions escalate faster
    const velocityBonus = (region.metrics.velocity / 100) * 10;  // Max 10 bonus points
    
    // Total score (capped at 100)
    const totalScore = Math.min(Math.max(volumeScore + trendScore + burstScore + alertScore + velocityBonus, 0), 100);
    
    return totalScore;
}

function renderMidnightClocks() {
    /**
     * Render SVG clock faces for dynamically discovered behavioral regions
     */
    if (!clustersData || !clustersData.clusters) return;
    
    // Discover behavioral regions from current clusters
    const regions = discoverBehavioralRegions(clustersData.clusters);
    
    // Get container
    const container = document.getElementById('midnight-clocks');
    if (!container) return;
    
    // Clear existing content
    container.innerHTML = '';
    
    // If no regions, show message
    if (regions.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: var(--text-muted);">No active coordination regions detected</p>';
        return;
    }
    
    // Render up to 5 most significant regions
    regions.slice(0, 5).forEach((region, idx) => {
        const score = computeMidnightScore(region);
        
        // Map score to clock time (0-100 → 6:00-12:00 on clock)
        const angle = 180 + (score / 100) * 180;  // 180° = 6:00, 360° = 12:00
        const radians = (angle - 90) * (Math.PI / 180);
        
        // Calculate hand endpoint
        const centerX = 60;
        const centerY = 60;
        const handLength = 40;
        const handX = centerX + handLength * Math.cos(radians);
        const handY = centerY + handLength * Math.sin(radians);
        
        // Color gradient based on score
        let color = '#26a641';  // Green
        if (score > 50) color = '#f9ab00';  // Amber
        if (score > 75) color = '#f85149';  // Red
        
        // Create SVG clock
        const svg = `
            <svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" style="width: 120px; height: 120px;">
                <circle cx="60" cy="60" r="55" fill="none" stroke="var(--border)" stroke-width="2"/>
                ${[...Array(12)].map((_, i) => {
                    const markerAngle = (i * 30 - 90) * (Math.PI / 180);
                    const markerX1 = 60 + 45 * Math.cos(markerAngle);
                    const markerY1 = 60 + 45 * Math.sin(markerAngle);
                    const markerX2 = 60 + 50 * Math.cos(markerAngle);
                    const markerY2 = 60 + 50 * Math.sin(markerAngle);
                    return `<line x1="${markerX1}" y1="${markerY1}" x2="${markerX2}" y2="${markerY2}" stroke="var(--border)" stroke-width="2"/>`;
                }).join('')}
                <circle cx="60" cy="10" r="3" fill="${color}" opacity="0.5"/>
                <line x1="${centerX}" y1="${centerY}" x2="${handX}" y2="${handY}" 
                      stroke="${color}" stroke-width="3" stroke-linecap="round"/>
                <circle cx="60" cy="60" r="4" fill="${color}"/>
            </svg>
        `;
        
        // Time display
        const timeDisplay = score === 0 ? '6:00' : score === 100 ? '12:00' : `~${(6 + (score/100) * 6).toFixed(1)}`;
        let interpretation = 'Calm';
        if (score > 25) interpretation = 'Some discussion';
        if (score > 50) interpretation = 'Active discussion';
        if (score > 75) interpretation = 'Elevated discussion';
        
        // Get representative ZIPs
        const zipList = region.clusters.map(c => c.zip).slice(0, 3).join(', ');
        const moreCount = region.clusters.length > 3 ? ` +${region.clusters.length - 3}` : '';
        
        // Coordination metrics summary
        const metricsTooltip = `
Velocity: ${region.metrics.velocity.toFixed(0)}/100 (time tolerance)
Density: ${region.metrics.density.toFixed(0)}/100 (signal concentration)
Negotiation: ${region.metrics.negotiation.toFixed(0)}/100 (rule variance)
Movement: ${region.metrics.movement.toFixed(0)}/100 (transit friction)
        `.trim();
        
        // Create clock card
        const clockCard = document.createElement('div');
        clockCard.className = 'clock-card';
        clockCard.innerHTML = `
            <div class="clock-widget" title="${metricsTooltip}">${svg}</div>
            <div class="clock-label">
                <strong style="color: ${color};">${timeDisplay}</strong><br>
                <span style="font-size: 0.9em; color: var(--text-muted);">${interpretation}</span>
            </div>
            <div class="clock-region">
                <strong>${region.profile}</strong><br>
                <small style="color: var(--text-muted);">${region.clusters.length} cluster${region.clusters.length !== 1 ? 's' : ''}</small><br>
                <small style="color: var(--text-muted);">ZIPs: ${zipList}${moreCount}</small>
            </div>
        `;
        
        // Add tooltip showing what this profile means
        clockCard.title = `${region.profile} — Score: ${score.toFixed(1)}/100\n${metricsTooltip}\n\nThis profile describes HOW communities coordinate under pressure, not WHO they are.`;
        
        container.appendChild(clockCard);
    });
    
    // Update neighbor advisory with live data
    updateNeighborAdvisory();
}

function updateNeighborAdvisory() {
    /**
     * Populate the shareable neighbor advisory with live data
     */
    const clusterCount = clustersData?.clusters?.length || 0;
    const trend = timelineData?.trend?.direction || 'stable';
    const trendMagnitude = timelineData?.trend?.magnitude || 0;
    
    // Get top ZIPs
    const zipCounts = {};
    (clustersData?.clusters || []).forEach(c => {
        const zip = String(c.zip).padStart(5, '0');
        zipCounts[zip] = (zipCounts[zip] || 0) + 1;
    });
    const topZips = Object.entries(zipCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([zip]) => zip)
        .join(', ') || 'Statewide';
    
    // Format trend text
    let trendText = trend;
    if (trend === 'increasing' && trendMagnitude > 0) {
        trendText = `Increasing (+${Math.round(trendMagnitude)}%)`;
    } else if (trend === 'decreasing' && trendMagnitude > 0) {
        trendText = `Decreasing (-${Math.round(trendMagnitude)}%)`;
    } else {
        trendText = 'Stable';
    }
    
    // Update advisory placeholders
    const countEl = document.getElementById('advisory-cluster-count');
    const trendEl = document.getElementById('advisory-trend');
    const zipsEl = document.getElementById('advisory-zips');
    
    if (countEl) countEl.textContent = clusterCount;
    if (trendEl) trendEl.textContent = trendText;
    if (zipsEl) zipsEl.textContent = topZips;
    
    // Wire up copy button
    const copyBtn = document.getElementById('copy-advisory-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const advisory = document.getElementById('neighbor-advisory');
            if (advisory) {
                const text = advisory.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    copyBtn.textContent = '✓ Copied!';
                    setTimeout(() => {
                        copyBtn.textContent = '📋 Copy to Clipboard';
                    }, 2000);
                }).catch(() => {
                    alert('Copy failed. Please select and copy manually.');
                });
            }
        });
    }
}

// ============================================
// Service Worker Registration
// ============================================

function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('sw.js')
            .then(reg => console.log('Service worker registered:', reg.scope))
            .catch(err => console.warn('SW registration failed:', err));
    }
}

// ============================================
// PWA Install Prompt
// ============================================

let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallBanner();
});

function showInstallBanner() {
    if (document.querySelector('.pwa-install-banner')) return;
    const banner = document.createElement('div');
    banner.className = 'pwa-install-banner';
    banner.innerHTML = `
        <span class="install-text">📲 Install HEAT for quick access</span>
        <button class="install-btn" onclick="installPWA()">Install</button>
        <button class="dismiss-btn" onclick="this.parentElement.remove()">✕</button>
    `;
    document.body.appendChild(banner);
}

async function installPWA() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log('PWA install:', outcome);
    deferredPrompt = null;
    document.querySelector('.pwa-install-banner')?.remove();
}

// ============================================
// WhatsApp Sharing
// ============================================

function shareViaWhatsApp() {
    const advisory = document.getElementById('neighbor-advisory');
    if (!advisory) return;
    const text = advisory.innerText || advisory.textContent;
    const encoded = encodeURIComponent(text);
    window.open(`https://wa.me/?text=${encoded}`, '_blank');
}

// ============================================
// SMS Alert Opt-In
// ============================================

function initSMSOptIn() {
    const form = document.getElementById('sms-optin-form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const phone = document.getElementById('sms-phone')?.value?.trim();
        const zip = document.getElementById('sms-zip')?.value?.trim();
        const statusEl = document.getElementById('sms-status');

        if (!phone || !zip) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger);">Please enter both phone number and ZIP code.</span>';
            return;
        }

        if (!/^\d{10,11}$/.test(phone)) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger);">Please enter a valid 10-digit phone number.</span>';
            return;
        }

        if (!/^\d{5}$/.test(zip)) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger);">Please enter a valid 5-digit ZIP code.</span>';
            return;
        }

        // Store locally (backend integration point)
        const subscribers = JSON.parse(localStorage.getItem('heat-sms-subscribers') || '[]');
        const exists = subscribers.some(s => s.phone === phone);
        if (exists) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--warning);">This number is already subscribed.</span>';
            return;
        }

        subscribers.push({ phone, zip, timestamp: new Date().toISOString() });
        localStorage.setItem('heat-sms-subscribers', JSON.stringify(subscribers));

        if (statusEl) {
            statusEl.innerHTML = '<span style="color: var(--success);">✅ Subscribed! You\'ll receive alerts for ZIP ' + zip + '.</span>';
        }

        // Clear form
        document.getElementById('sms-phone').value = '';
        document.getElementById('sms-zip').value = '';
    });
}

// ============================================
// Community Report Form
// ============================================

function initCommunityReport() {
    const form = document.getElementById('community-report-form');
    if (!form) return;

    // Set default date to today
    const dateInput = document.getElementById('report-date');
    if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const zip = document.getElementById('report-zip')?.value?.trim();
        const date = document.getElementById('report-date')?.value;
        const time = document.getElementById('report-time')?.value || 'unknown';
        const type = document.getElementById('report-type')?.value;
        const description = document.getElementById('report-description')?.value?.trim();
        const statusEl = document.getElementById('report-status');

        if (!zip || !date || !description) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger);">Please fill in all required fields.</span>';
            return;
        }

        if (!/^\d{5}$/.test(zip)) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger);">Please enter a valid 5-digit ZIP code.</span>';
            return;
        }

        if (description.length < 10) {
            if (statusEl) statusEl.innerHTML = '<span style="color: var(--danger);">Description must be at least 10 characters.</span>';
            return;
        }

        // Store locally (backend integration point)
        const reports = JSON.parse(localStorage.getItem('heat-community-reports') || '[]');
        reports.push({
            id: Date.now(),
            zip, date, time, type, description,
            status: 'pending_review',
            submitted: new Date().toISOString()
        });
        localStorage.setItem('heat-community-reports', JSON.stringify(reports));

        if (statusEl) {
            statusEl.innerHTML = `
                <div style="padding: 1rem; background: rgba(38, 166, 65, 0.1); border-left: 4px solid var(--success); border-radius: 8px;">
                    <strong>✅ Report Submitted</strong><br>
                    <span style="font-size: 0.9em; color: var(--text-muted);">Your report for ZIP ${zip} has been saved and will be reviewed. A 72-hour delay will be applied before it appears publicly.</span>
                </div>
            `;
        }

        // Reset form (except date)
        document.getElementById('report-description').value = '';
    });
}

// ============================================
// Route Safety Checker
// ============================================

function initRouteChecker() {
    const btn = document.getElementById('route-check-btn');
    if (!btn) return;

    btn.addEventListener('click', () => {
        const fromZip = document.getElementById('route-from')?.value?.trim();
        const toZip = document.getElementById('route-to')?.value?.trim();
        const resultEl = document.getElementById('route-result');

        if (!fromZip || !toZip || !/^\d{5}$/.test(fromZip) || !/^\d{5}$/.test(toZip)) {
            if (resultEl) resultEl.innerHTML = '<span style="color: var(--danger);">Please enter valid 5-digit ZIP codes.</span>';
            return;
        }

        if (!clustersData?.clusters) {
            if (resultEl) resultEl.innerHTML = '<span style="color: var(--text-muted);">No data loaded yet. Please wait for the map to load.</span>';
            return;
        }

        // Get coordinates for both ZIPs
        const fromCoords = ZIP_COORDS[fromZip];
        const toCoords = ZIP_COORDS[toZip];

        if (!fromCoords && !toCoords) {
            if (resultEl) resultEl.innerHTML = '<span style="color: var(--text-muted);">One or both ZIP codes are not in our coverage area.</span>';
            return;
        }

        // Find clusters near the route (within ~0.15 degrees of the line between ZIPs)
        const routeClusters = [];
        const from = fromCoords || [40.0583, -74.4057];
        const to = toCoords || [40.0583, -74.4057];

        clustersData.clusters.forEach(cluster => {
            const coords = getClusterCoordinates(cluster);
            const dist = pointToLineDistance(coords[0], coords[1], from[0], from[1], to[0], to[1]);
            if (dist < 0.15) { // ~10 miles from route
                routeClusters.push({
                    cluster,
                    distance: dist
                });
            }
        });

        // Generate result
        if (routeClusters.length === 0) {
            resultEl.innerHTML = `
                <div class="route-safe">
                    <strong>✅ No Active Reports on This Route</strong><br>
                    <span style="font-size: 0.9em;">No ICE-related reports found between ZIP ${fromZip} and ZIP ${toZip}.</span><br>
                    <span style="font-size: 0.85em; color: var(--text-muted);">Remember: no reports ≠ nothing happening. Always stay aware.</span>
                </div>
            `;
        } else if (routeClusters.length <= 2) {
            const zipList = [...new Set(routeClusters.map(r => String(r.cluster.zip).padStart(5, '0')))].join(', ');
            resultEl.innerHTML = `
                <div class="route-caution">
                    <strong>⚠️ ${routeClusters.length} Report(s) Near Your Route</strong><br>
                    <span style="font-size: 0.9em;">Active reports near ZIPs: ${zipList}</span><br>
                    <span style="font-size: 0.85em; color: var(--text-muted);">Consider checking the map for details. Exercise normal caution.</span>
                </div>
            `;
        } else {
            const zipList = [...new Set(routeClusters.map(r => String(r.cluster.zip).padStart(5, '0')))].join(', ');
            resultEl.innerHTML = `
                <div class="route-alert">
                    <strong>🔴 ${routeClusters.length} Reports Near Your Route</strong><br>
                    <span style="font-size: 0.9em;">Active reports near ZIPs: ${zipList}</span><br>
                    <span style="font-size: 0.85em; color: var(--text-muted);">Multiple reports near this route. Review the map for specifics and consider alternatives if possible.</span>
                </div>
            `;
        }
    });
}

// Helper: point-to-line distance (geographic approximation)
function pointToLineDistance(px, py, x1, y1, x2, y2) {
    const A = px - x1;
    const B = py - y1;
    const C = x2 - x1;
    const D = y2 - y1;
    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    let param = lenSq !== 0 ? dot / lenSq : -1;

    let xx, yy;
    if (param < 0) { xx = x1; yy = y1; }
    else if (param > 1) { xx = x2; yy = y2; }
    else { xx = x1 + param * C; yy = y1 + param * D; }

    return Math.sqrt((px - xx) ** 2 + (py - yy) ** 2);
}

// ============================================
// Bottom Navigation
// ============================================

function initBottomNav() {
    const nav = document.getElementById('bottom-nav');
    if (!nav) return;

    const items = nav.querySelectorAll('.bottom-nav-item');

    items.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = item.dataset.section;
            const section = document.getElementById(sectionId);
            if (section) {
                section.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Haptic
                if (navigator.vibrate) navigator.vibrate(10);
            }
            // Update active
            items.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });

    // Update active on scroll
    const sectionIds = Array.from(items).map(i => i.dataset.section);
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const scrollPos = window.scrollY + window.innerHeight / 3;
                let activeId = sectionIds[0];

                sectionIds.forEach(id => {
                    const section = document.getElementById(id);
                    if (section && section.offsetTop <= scrollPos) {
                        activeId = id;
                    }
                });

                items.forEach(item => {
                    item.classList.toggle('active', item.dataset.section === activeId);
                });
                ticking = false;
            });
            ticking = true;
        }
    });
}

// ============================================
// Copy Advisory (fixed clipboard API)
// ============================================

function initCopyAdvisory() {
    const btn = document.getElementById('copy-advisory-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
        const advisory = document.getElementById('neighbor-advisory');
        if (!advisory) return;

        const text = advisory.innerText || advisory.textContent;
        try {
            await navigator.clipboard.writeText(text);
            btn.textContent = '✅ Copied!';
            setTimeout(() => { btn.textContent = '📋 Copy to Clipboard'; }, 2000);
        } catch {
            // Fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            btn.textContent = '✅ Copied!';
            setTimeout(() => { btn.textContent = '📋 Copy to Clipboard'; }, 2000);
        }
    });
}

// ============================================
// WhatsApp Share Button Init
// ============================================

function initWhatsAppShare() {
    const btn = document.getElementById('whatsapp-share-btn');
    if (btn) {
        btn.addEventListener('click', shareViaWhatsApp);
    }
}

// ============================================
// Expanded Translations for New Sections
// ============================================

// Merge additional translation keys
Object.assign(TRANSLATIONS.en, {
    smsSignup: "SMS Alert Signup",
    smsDescription: "Get text alerts when new ICE-related reports appear near your ZIP code. Free, no app needed.",
    subscribe: "Subscribe",
    submitReport: "Submit a Community Report",
    reportDescription: "Help keep your community informed. Reports are reviewed before appearing publicly.",
    routeChecker: "Route Safety Checker",
    routeDescription: "Check if there are active reports along your travel route.",
    checkRoute: "Check Route",
    map: "Map",
    stats: "Stats",
    safety: "Safety",
    report: "Report",
    route: "Route",
    installPrompt: "Install HEAT for quick access",
    install: "Install"
});

Object.assign(TRANSLATIONS.es, {
    smsSignup: "Registro de Alertas SMS",
    smsDescription: "Reciba alertas de texto cuando se reporten temas de ICE cerca de su código postal. Gratis, sin app.",
    subscribe: "Suscribirse",
    submitReport: "Enviar un Reporte Comunitario",
    reportDescription: "Ayude a mantener informada a su comunidad. Los reportes se revisan antes de publicarse.",
    routeChecker: "Verificador de Seguridad de Ruta",
    routeDescription: "Verifique si hay reportes activos en su ruta de viaje.",
    checkRoute: "Verificar Ruta",
    map: "Mapa",
    stats: "Estadísticas",
    safety: "Seguridad",
    report: "Reporte",
    route: "Ruta",
    installPrompt: "Instalar HEAT para acceso rápido",
    install: "Instalar"
});

// ============================================
// Initialization
// ============================================

document.addEventListener("DOMContentLoaded", async () => {
    // Convenience helper — bus may not be ready if module hasn't loaded yet
    const _bus = () => window.HeatAgentBus;

    try {
        _bus()?.agentStart('app', { phase: 'init' });

        // Check if running via file:// protocol (which causes CORS issues)
        if (window.location.protocol === 'file:') {
            const errorMsg = `
                ⚠️ ERROR: This app must be run through a web server!
                
                Please use one of these options:
                1. Double-click "start-server.bat" in the build folder
                2. Or run: python -m http.server 8080
                3. Then open: http://localhost:8080
                
                Opening HTML files directly (file://) causes CORS errors.
            `;
            console.error(errorMsg);
            alert(errorMsg);
            showError("This app must be run through a web server. See console (F12) for instructions.");
            return;
        }
        
        console.log("HEAT Dashboard initializing...");
        console.log("Protocol:", window.location.protocol);
        console.log("URL:", window.location.href);
        
        // Show loading state immediately
        showLoading("Loading HEAT map data...");
        
        // Load saved language
        currentLanguage = localStorage.getItem('heat-language') || 'en';

        initThemeToggle();
        initLanguageSelector();
        initSearch();
        initKeyboardNavigation();  // NEW: keyboard navigation
        setupRegionNavigation();  // Setup region buttons
        
        // Initialize keyword region display
        const regionDisplayText = document.getElementById('keyword-current-region');
        if (regionDisplayText) {
            regionDisplayText.textContent = 'Statewide';
        }
        
        initMap();
        
        // NEW: Setup reset map button
        const resetBtn = document.getElementById('reset-map');
        if (resetBtn) {
            resetBtn.addEventListener('click', resetMapView);
        }
        
        // NEW: Setup retry button
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', async () => {
                hideError();
                showLoading("Retrying...");
                try {
                    await loadData();
                    // Re-render everything
                    renderMap();
                    renderClusters();
                    renderTimeline();
                    renderKeywords(currentRegion);
                    updateLastUpdated();
                    updateDashboard();
                    updateQuickStats();
                    renderSidebar();
                    hideLoading();
                    announceToScreenReader("Data loaded successfully");
                } catch (error) {
                    showError("Still unable to load data. Please check your connection.");
                    announceToScreenReader("Failed to load data");
                }
            });
        }
        
        await loadData();
        
        // Hide loading and show success
        hideLoading();
        announceToScreenReader("Map loaded with " + (clustersData?.clusters?.length || 0) + " active reports");

        // Wrap each render function in try-catch to prevent crashes
        // renderLatestNews() — replaced by renderSidebar() which populates the sidebar news list
        try { renderAlertsBanner(); } catch (e) { console.error('Alert banner render failed:', e); }
        try { renderMap(); } catch (e) { console.error('Map render failed:', e); }
        try { renderClusters(); } catch (e) { console.error('Clusters render failed:', e); }
        try { renderTimeline(); } catch (e) { console.error('Timeline render failed:', e); }
        try { renderKeywords(currentRegion); } catch (e) { console.error('Keywords render failed:', e); }
        try { updateLastUpdated(); } catch (e) { console.error('Last updated failed:', e); }
        try { updateDashboard(); } catch (e) { console.error('Dashboard update failed:', e); }
        try { updateQuickStats(); } catch (e) { console.error('Quick stats update failed:', e); }
        try { renderSidebar(); } catch (e) { console.error('Sidebar render failed:', e); }
        try { wireSidebarToMap(); } catch (e) { console.error('Sidebar-map wiring failed:', e); }

        try { initSafeCheck(); } catch (e) { console.error('Safe check init failed:', e); }
        try { initMobilePanel(); } catch (e) { console.error('Mobile panel init failed:', e); }
        try { populateMobileFeed(); } catch (e) { console.error('Mobile feed populate failed:', e); }
        try { init3DToggle(); } catch (e) { console.error('3D toggle init failed:', e); }
        try { initKeywordControls(); } catch (e) { console.error('Keyword controls init failed:', e); }
        try { initEventTracking(); } catch (e) { console.error('Event tracking init failed:', e); }
        try { initTimelineSlider(); } catch (e) { console.error('Timeline slider init failed:', e); }
        try { initHeatmapLayer(); } catch (e) { console.error('Heatmap layer init failed:', e); }
        try { initDashboardClicks(); } catch (e) { console.error('Dashboard clicks init failed:', e); }
        try { initGeolocation(); } catch (e) { console.error('Geolocation init failed:', e); }
        try { initCollapsibleSections(); } catch (e) { console.error('Collapsible sections init failed:', e); }
        try { updateUILanguage(); } catch (e) { console.error('UI language update failed:', e); }
        try { renderMidnightClocks(); } catch (e) { console.error('Midnight clocks render failed:', e); }
        try { registerServiceWorker(); } catch (e) { console.error('SW registration failed:', e); }
        try { initBottomNav(); } catch (e) { console.error('Bottom nav init failed:', e); }
        try { initCopyAdvisory(); } catch (e) { console.error('Copy advisory init failed:', e); }
        try { initWhatsAppShare(); } catch (e) { console.error('WhatsApp share init failed:', e); }
        try { initSMSOptIn(); } catch (e) { console.error('SMS opt-in init failed:', e); }
        try { initCommunityReport(); } catch (e) { console.error('Community report init failed:', e); }
        try { initRouteChecker(); } catch (e) { console.error('Route checker init failed:', e); }
        try { initAnalyticsIntegration(); } catch (e) { console.error('Analytics initialization failed:', e); }
        try { initVulnerabilityLayer(); } catch (e) { console.error('Vulnerability layer init failed:', e); }
        try { initKDELayer(); } catch (e) { console.error('KDE layer init failed:', e); }
        try { initHotspotsLayer(); } catch (e) { console.error('Hotspots layer init failed:', e); }
        try { initSpatialClustersLayer(); } catch (e) { console.error('Spatial clusters layer init failed:', e); }
        try { initPropagationLayer(); } catch (e) { console.error('Propagation layer init failed:', e); }
        try { initStabilityMode(); } catch (e) { console.error('Stability mode init failed:', e); }
        try { initWebSocket(); } catch (e) { console.error('WebSocket init failed:', e); }

        _bus()?.agentComplete('app', {
            phase: 'init',
            clusters: clustersData?.clusters?.length || 0,
        });
    } catch (error) {
        _bus()?.agentError('app', error.message, { phase: 'init' });
        console.error('Fatal initialization error:', error);
        // Show error message to user
        showError("Unable to initialize the map. Please refresh the page.");
        announceToScreenReader("Error loading map data");
const loadingMsg = document.querySelector('.loading-message');
        if (loadingMsg) {
            loadingMsg.textContent = 'Error loading data. Please refresh the page.';
            loadingMsg.style.color = 'red';
        }
    }
});

// ============================================
// Language Selector
// ============================================

function initLanguageSelector() {
    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.value = currentLanguage;
        langSelect.addEventListener('change', (e) => {
            setLanguage(e.target.value);
        });
    }
}

// ============================================
// Search Functionality
// ============================================

function initSearch() {
    const searchInput = document.getElementById('search-input');
    const searchClear = document.getElementById('search-clear');
    const searchResults = document.getElementById('search-results');
    
    if (!searchInput) return;
    
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        // Toggle clear button
        if (searchClear) {
            searchClear.classList.toggle('hidden', query.length === 0);
        }
        
        if (query.length < 2) {
            if (searchResults) searchResults.classList.add('hidden');
            return;
        }
        
        performSearch(query);
    });
    
    searchInput.addEventListener('focus', (e) => {
        if (e.target.value.length >= 2) {
            performSearch(e.target.value.trim());
        }
    });
    
    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container') && searchResults) {
            searchResults.classList.add('hidden');
        }
    });
    
    if (searchClear) {
        searchClear.addEventListener('click', () => {
            searchInput.value = '';
            searchClear.classList.add('hidden');
            if (searchResults) searchResults.classList.add('hidden');
        });
    }
}

function performSearch(query) {
    const results = [];
    const q = query.toLowerCase();
    
    // Search ZIPs - show all ZIPs in ZIP_BOUNDARIES
    Object.keys(ZIP_BOUNDARIES).forEach(zip => {
        if (zip.includes(q)) {
            results.push({
                type: 'zip',
                label: `ZIP ${zip}`,
                icon: '📍',
                data: { zip }
            });
        }
    });
    
    // If query looks like a ZIP code (5 digits), add it even if not in boundaries
    if (/^\d{5}$/.test(q) && !Object.keys(ZIP_BOUNDARIES).some(z => z === q)) {
        const zipNum = parseInt(q, 10);
        const isNJ = (zipNum >= 7001 && zipNum <= 8989);
        results.push({
            type: 'zip',
            label: `ZIP ${q}${isNJ ? ' (NJ)' : ' (Out of state)'}`,
            icon: '📍',
            data: { zip: q }
        });
    }
    
    // Search streets
    Object.keys(STREET_COORDS).forEach(street => {
        if (street.includes(q)) {
            const streetData = STREET_COORDS[street];
            results.push({
                type: 'street',
                label: street.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
                icon: '🛣️',
                data: { lat: streetData.lat, lng: streetData.lng }
            });
        }
    });
    
    // Search clusters
    if (clustersData?.clusters) {
        clustersData.clusters.forEach(cluster => {
            const summary = (cluster.summary || '').toLowerCase();
            if (summary.includes(q)) {
                results.push({
                    type: 'cluster',
                    label: `Cluster #${cluster.id}: ${cluster.summary.substring(0, 40)}...`,
                    icon: '🔥',
                    data: { cluster }
                });
            }
        });
    }
    
    renderSearchResults(results);
}

function renderSearchResults(results) {
    const container = document.getElementById('search-results');
    if (!container) return;
    
    if (results.length === 0) {
        container.innerHTML = `
            <div class="search-no-results">
                ${t('noResults')}
                <small>${t('tryAgain')}</small>
            </div>
        `;
        container.classList.remove('hidden');
        return;
    }
    
    container.innerHTML = results.slice(0, 8).map(result => `
        <div class="search-result-item" data-type="${result.type}" data-result='${JSON.stringify(result.data)}'>
            <span class="result-icon">${result.icon}</span>
            <span class="result-label">${result.label}</span>
            <span class="result-type">${t(result.type === 'zip' ? 'zipCode' : result.type)}</span>
        </div>
    `).join('');
    
    // Add click handlers
    container.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const type = item.dataset.type;
            const data = JSON.parse(item.dataset.result);
            handleSearchSelect(type, data);
            container.classList.add('hidden');
        });
    });
    
    container.classList.remove('hidden');
}

function handleSearchSelect(type, data) {
    if (!map) return;
    
    if (type === 'zip') {
        const zipData = ZIP_BOUNDARIES[data.zip];
        if (zipData) {
            // ZIP has detailed boundaries - fly to it
            map.flyTo(zipData.center, 15, { duration: 0.8 });
        } else if (ZIP_COORDS[data.zip]) {
            // ZIP has coordinates - fly to them
            map.flyTo(ZIP_COORDS[data.zip], 13, { duration: 0.8 });
        } else {
            // ZIP not in our coordinate system - check safety and zoom to NJ
            const zipNum = parseInt(data.zip, 10);
            const isNJ = (zipNum >= 7001 && zipNum <= 8989);
            if (isNJ) {
                // Valid NJ ZIP - open Check Your Area panel and check it
                const panel = document.getElementById("safe-check-panel");
                const zipInput = document.getElementById("safe-check-zip");
                const toggleBtn = document.getElementById("safe-check-toggle");
                
                if (panel && zipInput) {
                    panel.classList.remove("hidden");
                    if (toggleBtn) toggleBtn.textContent = "✕ Close";
                    zipInput.value = data.zip;
                    checkZipSafety(data.zip);
                }
                
                // Zoom to NJ center
                map.flyTo(DEFAULT_CENTER, 9, { duration: 0.8 });
            } else {
                // Out of state ZIP - just show message
                alert(`ZIP ${data.zip} is outside New Jersey. This tool covers NJ only.`);
            }
        }
    } else if (type === 'street') {
        map.flyTo([data.lat, data.lng], 16, { duration: 0.8 });
    } else if (type === 'cluster') {
        const coords = getClusterCoordinates(data.cluster);
        map.flyTo(coords, 15, { duration: 0.8 });
        
        // Highlight the cluster card
        const card = document.querySelector(`[data-cluster-id="${data.cluster.id}"]`);
        if (card) {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            card.classList.add('highlighted');
            setTimeout(() => card.classList.remove('highlighted'), 2000);
        }
    }
}

// ============================================
// Collapsible Sections
// ============================================

function initCollapsibleSections() {
    document.querySelectorAll('.section-header.clickable').forEach(header => {
        header.addEventListener('click', () => {
            const content = header.nextElementSibling;
            const icon = header.querySelector('.expand-icon');
            
            if (content?.classList.contains('section-content')) {
                content.classList.toggle('collapsed');
                if (icon) {
                    icon.textContent = content.classList.contains('collapsed') ? '▼' : '▲';
                }
            }
        });
    });
}

// ============================================
// Theme Toggle (Light/Dark Mode)
// ============================================

function initThemeToggle() {
    const themeToggle = document.getElementById("theme-toggle");
    const themeColorMeta = document.getElementById("theme-color-meta");
    
    // Check for saved theme preference
    const savedTheme = localStorage.getItem("heat-theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
    updateThemeIcon(savedTheme);
    
    themeToggle?.addEventListener("click", () => {
        const currentTheme = document.documentElement.getAttribute("data-theme");
        const newTheme = currentTheme === "dark" ? "light" : "dark";
        
        document.documentElement.setAttribute("data-theme", newTheme);
        localStorage.setItem("heat-theme", newTheme);
        updateThemeIcon(newTheme);
        
        // Update theme-color meta for iOS
        if (themeColorMeta) {
            themeColorMeta.content = newTheme === "light" ? "#ffffff" : "#202124";
        }
        
        // Update map tiles to match theme
        if (map) {
            updateMapTiles();
        }
    });
}

function updateThemeIcon(theme) {
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
        themeToggle.textContent = theme === "light" ? "🌙" : "☀️";
    }
}

// ============================================
// Geolocation (iOS Native)
// ============================================

function initGeolocation() {
    const locationBtn = document.getElementById("location-btn");
    const userLocationDiv = document.getElementById("user-location");
    const userZipSpan = document.getElementById("user-zip");
    
    locationBtn?.addEventListener("click", () => {
        if ("geolocation" in navigator) {
            locationBtn.textContent = "⏳";
            navigator.geolocation.getCurrentPosition(
                async (position) => {
                    const { latitude, longitude } = position.coords;
                    
                    // Simple ZIP detection based on Plainfield area
                    const zip = detectZipFromCoords(latitude, longitude);
                    
                    if (zip) {
                        userZipSpan.textContent = zip;
                        userLocationDiv.classList.remove("hidden");
                        highlightUserZip(zip);
                        renderAlertsBanner(zip);
                        localStorage.setItem("heat-user-zip", zip);
                    }
                    locationBtn.textContent = "📍";
                },
                (error) => {
                    console.warn("Geolocation error:", error);
                    locationBtn.textContent = "❌";
                    setTimeout(() => { locationBtn.textContent = "📍"; }, 2000);
                },
                { enableHighAccuracy: true }
            );
        }
    });
    
    // Load saved ZIP
    const savedZip = localStorage.getItem("heat-user-zip");
    if (savedZip) {
        userZipSpan.textContent = savedZip;
        userLocationDiv.classList.remove("hidden");
        renderAlertsBanner(savedZip);
    }
}

function detectZipFromCoords(lat, lng) {
    // Proximity check against known ZIP centroids (Plainfield + Edison, extensible)
    const zips = Object.entries(ZIP_COORDS).map(([zip, [zlat, zlng]]) => ({ zip, lat: zlat, lng: zlng }));
    
    let closest = null;
    let minDist = Infinity;
    
    zips.forEach(z => {
        const dist = Math.sqrt(Math.pow(lat - z.lat, 2) + Math.pow(lng - z.lng, 2));
        if (dist < minDist) {
            minDist = dist;
            closest = z.zip;
        }
    });
    
    // Threshold ~0.2 degrees (~14 miles) to avoid wrong assignments
    return minDist < 0.2 ? closest : null;
}

function highlightUserZip(zip) {
    // Highlight clusters in user's ZIP
    if (!clustersData?.clusters) return;
    
    const userClusters = clustersData.clusters.filter(c => 
        String(c.zip).padStart(5, '0') === zip
    );
    
    if (userClusters.length > 0) {
        const userLocationDiv = document.getElementById("user-location");
        userLocationDiv.innerHTML = `
            <span>📍 Your area: <strong>${zip}</strong> — ${userClusters.length} signal(s) nearby</span>
        `;
    }
}

// ============================================
// Quick Dashboard
// ============================================

function updateDashboard() {
    const clusterCount = clustersData?.clusters?.length || 0;
    const trend = timelineData?.trend?.direction || "stable";
    const keywordCount = keywordsData?.keywords?.length || keywordsData?.top_keywords?.length || 0;
    
    // Calculate intensity (0-100)
    let intensity = 0;
    if (clustersData?.clusters) {
        const totalStrength = clustersData.clusters.reduce((sum, c) => sum + (c.strength || 0), 0);
        intensity = Math.min(100, Math.round(totalStrength * 10));
    }
    
    // Update dashboard values
    document.getElementById("dash-clusters").textContent = clusterCount;
    document.getElementById("dash-trend").textContent = trend === "increasing" ? "↑ Rising" : 
                                                        trend === "decreasing" ? "↓ Falling" : "→ Stable";
    document.getElementById("dash-keywords").textContent = keywordCount;
    document.getElementById("dash-intensity").textContent = intensity + "%";
    
    // Animate intensity bar
    const intensityFill = document.getElementById("intensity-fill");
    if (intensityFill) {
        setTimeout(() => {
            intensityFill.style.width = intensity + "%";
        }, 300);
    }

    // Update entropy gauge (Shift 10)
    updateEntropyGauge();
}

function updateEntropyGauge() {
    const cei = entropyData?.system?.cei ?? null;
    const dashEl = document.getElementById("dash-entropy");
    const arcEl = document.getElementById("entropy-arc-fill");

    if (dashEl) {
        dashEl.textContent = cei !== null ? cei : "--";
    }

    if (arcEl && cei !== null) {
        // Arc total length ≈ 50.27  (π * 16)
        const arcLen = Math.PI * 16;
        const filled = (cei / 100) * arcLen;
        setTimeout(() => {
            arcEl.style.strokeDasharray = `${filled} ${arcLen}`;
            // Color based on CEI level
            if (cei >= 70) {
                arcEl.style.stroke = "var(--danger, #f85149)";
            } else if (cei >= 40) {
                arcEl.style.stroke = "var(--warning, #d29922)";
            } else {
                arcEl.style.stroke = "var(--accent, #58a6ff)";
            }
        }, 400);
    }
}

function initDashboardClicks() {
    document.querySelectorAll(".dash-card").forEach(card => {
        card.addEventListener("click", () => {
            const target = card.dataset.target;
            const section = document.getElementById(target);
            if (section) {
                section.scrollIntoView({ behavior: "smooth", block: "start" });
                
                // Haptic feedback on iOS
                if (navigator.vibrate) {
                    navigator.vibrate(10);
                }
            }
        });
    });
}

// ============================================
// Map Functions
// ============================================

let tileLayer;

function initMap() {
    map = L.map("map", {
        center: DEFAULT_CENTER,
        zoom: DEFAULT_ZOOM,
        scrollWheelZoom: true,
    });
    
    // Initialize with light theme tile layer
    updateMapTiles();
}

function updateMapTiles() {
    const theme = document.documentElement.getAttribute("data-theme");
    
    // Remove existing tile layer
    if (tileLayer) {
        map.removeLayer(tileLayer);
    }
    
    // Add appropriate tile layer based on theme
    if (theme === "light") {
        tileLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: "abcd",
            maxZoom: 19,
        }).addTo(map);
    } else {
        tileLayer = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: "abcd",
            maxZoom: 19,
        }).addTo(map);
    }
}

function renderMap() {
    console.log("renderMap called, clustersData:", clustersData);
    
    // Clear existing markers
    clusterMarkers.forEach(marker => map.removeLayer(marker));
    clusterMarkers = [];
    
    if (!clustersData || !clustersData.clusters || clustersData.clusters.length === 0) {
        console.log("No clusters data available");
        // Add a default marker showing the area
        L.circleMarker(PLAINFIELD_CENTER, {
            radius: 20,
            fillColor: "#58a6ff",
            color: "#fff",
            weight: 2,
            opacity: 0.8,
            fillOpacity: 0.3,
        })
        .bindPopup("<strong>Plainfield, NJ</strong><br>No active ICE attention clusters at this time.")
        .addTo(map);
        return;
    }
    
    console.log(`Rendering ${clustersData.clusters.length} clusters`);
    
    // Add cluster markers from oldest to newest so recent ones appear on top
    // (Leaflet draws markers in order, so last added appears on top)
    const clustersForMap = [...clustersData.clusters].reverse(); // Reverse the sorted array
    const markers = [];
    clustersForMap.forEach((cluster, idx) => {
        try {
            const marker = addClusterMarker(cluster);
            if (marker) {
                markers.push(marker);
                clusterMarkers.push(marker);
            }
            if (idx < 3) console.log(`Cluster ${idx}:`, cluster.zip, marker ? 'rendered' : 'failed');
        } catch (e) {
            console.error(`Error rendering cluster ${idx}:`, e, cluster);
        }
    });
    
    console.log(`Successfully rendered ${markers.length} markers`);
    
    // Auto-fit map to show all clusters (with reasonable bounds)
    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        const bounds = group.getBounds();
        
        // Only auto-fit if we have clusters spread across multiple locations
        // Otherwise just center on the clusters at a reasonable zoom
        const latRange = bounds.getNorth() - bounds.getSouth();
        const lngRange = bounds.getEast() - bounds.getWest();
        
        if (latRange > 0.01 || lngRange > 0.01) {
            // Clusters are spread out - fit to show all with padding
            map.fitBounds(bounds.pad(0.2), { maxZoom: 11 });
        } else {
            // Clusters are very close together - just center with zoom
            map.setView(bounds.getCenter(), 12);
        }
    } else {
        // No clusters - show default NJ statewide view
        map.setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    }
    
    // Force map to redraw
    setTimeout(() => map.invalidateSize(), 100);
}

function addClusterMarker(cluster) {
    // Use intelligent positioning based on cluster content
    const coords = getClusterCoordinates(cluster);
    
    // Check if recent activity (within last 48 hours)
    const endDate = new Date(cluster.dateRange.end);
    const now = new Date();
    const hoursSinceEnd = (now - endDate) / (1000 * 60 * 60);
    const isRecent = hoursSinceEnd <= 48;
    
    // Size based on cluster size and strength
    const baseRadius = 15;
    const sizeBonus = Math.min(cluster.size * 2, 15);
    const strengthBonus = Math.min(cluster.strength * 3, 15);
    const radius = baseRadius + sizeBonus + strengthBonus;
    
    // Color based on strength - Google-style pastels
    let color, fillColor;
    if (cluster.strength > 5) {
        color = "#ee675c";
        fillColor = "#ea4335";
    } else if (cluster.strength > 2) {
        color = "#f9ab00";
        fillColor = "#fbbc04";
    } else {
        color = "#81c995";
        fillColor = "#34a853";
    }
    
    // Make recent activity more prominent
    const markerOptions = {
        radius: radius,
        fillColor: fillColor,
        color: color,
        weight: isRecent ? 5 : 3,  // Thicker border for recent
        opacity: isRecent ? 1.0 : 0.9,
        fillOpacity: isRecent ? 0.6 : 0.4,
        className: isRecent ? 'recent-marker pulse' : ''
    };
    
    const marker = L.circleMarker(coords, markerOptions).addTo(map);
    
    // Popup content with status and timestamps
    const status = getSignalStatus(cluster.dateRange.end);
    const relativeTime = getRelativeTime(cluster.dateRange.end);
    const lastReportDate = new Date(cluster.dateRange.end).toLocaleDateString("en-US", { 
        month: "short", 
        day: "numeric", 
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
    
    const mediaLinksHtml = cluster.mediaLinks?.length > 0 
        ? `<div style="margin-top: 8px; border-top: 1px solid var(--border); padding-top: 8px;">
            <strong>📰 Media Links:</strong><br>
            ${cluster.mediaLinks.slice(0, 3).map(url => {
                try {
                    const domain = new URL(url).hostname.replace('www.', '');
                    return `<a href="${url}" target="_blank" rel="noopener" style="color: var(--accent); font-size: 0.8em; display: block; margin: 2px 0; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">🔗 ${domain}</a>`;
                } catch {
                    return `<a href="${url}" target="_blank" rel="noopener" style="color: var(--accent); font-size: 0.8em; display: block; margin: 2px 0; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">🔗 Link</a>`;
                }
            }).join('')}
           </div>` 
        : '';

    const sourceType = cluster.source_type || cluster.sourceType || cluster.qualification || null;
    const sourceTypeLabel = sourceType ? escapeHtml(String(sourceType)) : "Vetted public / qualified community";
    const recentBadge = isRecent ? '<span style="background: #ff4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; margin-left: 4px;">🔥 NEW</span>' : '';
    
    const popupContent = `
        <div style="background: var(--bg); color: var(--text); padding: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong style="font-size: 1.1em;">Cluster #${cluster.id}${recentBadge}</strong>
                <span style="background: ${status.color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; font-weight: bold;">
                    ${status.icon} ${status.label}
                </span>
            </div>
            <small style="color: var(--text-muted);">ZIP: ${cluster.zip}</small><br><br>
            
            <div style="background: var(--bg-secondary); padding: 8px; border-radius: 8px; margin: 8px 0;">
                <div style="font-size: 0.9em; margin-bottom: 4px;">
                    📊 <strong>${cluster.size}</strong> signals &nbsp;|&nbsp; 🔥 Strength: <strong>${cluster.strength.toFixed(1)}</strong>
                </div>
            </div>
            
            <em style="font-size: 0.85em; color: var(--text-muted);">"${truncate(cluster.summary, 120)}"</em><br><br>
            
            <div style="background: var(--bg-tertiary); padding: 8px; border-radius: 8px; font-size: 0.85em;">
                <div style="margin-bottom: 4px;">
                    <strong>⏰ Last Report:</strong> ${relativeTime}
                </div>
                <div style="color: var(--text-muted); font-size: 0.9em;">
                    ${lastReportDate}
                </div>
                <div style="color: var(--text-muted); font-size: 0.85em; margin-top: 4px;">
                    📅 Period: ${formatDateRange(cluster.dateRange.start, cluster.dateRange.end)}
                </div>
                <div style="color: var(--text-muted); font-size: 0.85em; margin-top: 4px;">
                    🧾 Source type: ${sourceTypeLabel}
                </div>
                <div style="color: var(--text-muted); font-size: 0.85em; margin-top: 4px;">
                    🧭 Interpretive signal — verify independently
                </div>
            </div>
            ${mediaLinksHtml}
        </div>
    `;
    
    marker.bindPopup(popupContent, {
        maxWidth: 280,
    });
    
    return marker;
}

// ============================================
// Data Loading
// ============================================

async function loadData() {
    const _bus = () => window.HeatAgentBus;
    try {
        _bus()?.agentStart('app', { phase: 'loadData' });
        showLoading("Loading data...");
        
        // Detect if we're on CloudFront or S3 and adjust paths accordingly
        const baseUrl = getBaseUrl();
        const cacheBuster = `?t=${Date.now()}`;
        
        console.log("Loading data from base URL:", baseUrl);
        
        const [clustersRes, timelineRes, keywordsRes, alertsRes, latestNewsRes, entropyRes] = await Promise.all([
            fetch(baseUrl + "data/clusters.json" + cacheBuster, { cache: "no-store" }),
            fetch(baseUrl + "data/timeline.json" + cacheBuster, { cache: "no-store" }),
            fetch(baseUrl + "data/keywords.json" + cacheBuster, { cache: "no-store" }),
            fetch(baseUrl + "data/alerts.json" + cacheBuster, { cache: "no-store" }),
            fetch(baseUrl + "data/latest_news.json" + cacheBuster, { cache: "no-store" }),
            fetch(baseUrl + "data/entropy.json" + cacheBuster, { cache: "no-store" }).catch(() => null),
        ]);
        
        console.log("Fetch responses:", {
            clusters: clustersRes.status,
            timeline: timelineRes.status,
            keywords: keywordsRes.status,
            alerts: alertsRes.status,
            latestNews: latestNewsRes.status
        });
        
        if (clustersRes.ok) {
            clustersData = await clustersRes.json();
            // Sort clusters by most recent activity first (dateRange.end descending)
            if (clustersData?.clusters?.length > 0) {
                clustersData.clusters.sort((a, b) => {
                    const dateA = new Date(a.dateRange?.end || 0);
                    const dateB = new Date(b.dateRange?.end || 0);
                    return dateB - dateA; // Most recent first
                });
            }
            console.log("Loaded clusters (sorted by most recent):", clustersData);
        } else {
            console.warn("Could not load clusters.json");
            clustersData = { clusters: [] };
        }
        
        if (timelineRes.ok) {
            timelineData = await timelineRes.json();
            console.log("Loaded timeline:", timelineData);
        } else {
            console.warn("Could not load timeline.json");
            timelineData = { weeks: [] };
        }
        
        if (keywordsRes.ok) {
            keywordsData = await keywordsRes.json();
            console.log("Loaded keywords:", keywordsData);
        } else {
            console.warn("Could not load keywords.json");
            keywordsData = null;
        }
        
        if (alertsRes.ok) {
            alertsData = await alertsRes.json();
            console.log("Loaded alerts:", alertsData);
        } else {
            console.warn("Could not load alerts.json");
            alertsData = { alerts: [] };
        }
        
        if (latestNewsRes.ok) {
            latestNewsData = await latestNewsRes.json();
            console.log("Loaded latest news:", latestNewsData);
        } else {
            console.warn("Could not load latest_news.json");
            latestNewsData = { items: [] };
        }

        if (entropyRes && entropyRes.ok) {
            entropyData = await entropyRes.json();
            console.log("Loaded entropy:", entropyData);
        } else {
            entropyData = null;
        }

        snapshotAnalyticsBaseData();
        if (analyticsInitialized) {
            initAnalyticsIntegration();
        }

        updateDownloadSection();
        hideLoading();
        hideError();

        _bus()?.agentComplete('app', {
            phase: 'loadData',
            records: clustersData?.clusters?.length || 0,
        });
        
    } catch (error) {
        _bus()?.agentError('app', error.message, { phase: 'loadData' });
        console.error("Failed to load data:", error);
        console.error("Error details:", {
            name: error.name,
            message: error.message,
            stack: error.stack
        });
        
        // Check for CORS errors specifically
        if (error.message && error.message.includes('CORS') || error.name === 'TypeError') {
            const corsErrorMsg = `
                ⚠️ CORS Error Detected!
                
                This usually means you're opening the file directly (file://).
                Please run through a web server:
                1. Double-click "start-server.bat" in the build folder
                2. Or run: python -m http.server 8080
                3. Then open: http://localhost:8080
            `;
            console.error(corsErrorMsg);
            showError("CORS Error: Please run through a web server. See console (F12) for details.");
        } else {
            showError("Unable to load data. Please check your connection and try again. Error: " + error.message);
        }
        
        clustersData = { clusters: [] };
        timelineData = { weeks: [] };
        alertsData = { alerts: [] };
        latestNewsData = { items: [] };
        snapshotAnalyticsBaseData();
        updateDownloadSection();
        throw error;  // Re-throw to let initialization know it failed
    }
}

function updateDownloadSection() {
    const countEl = document.getElementById("download-count");
    const updatedEl = document.getElementById("download-updated");
    const jsonLink = document.getElementById("download-json");
    const csvLink = document.getElementById("download-csv");
    const openLink = document.getElementById("download-open");
    if (!countEl || !updatedEl) return;

    const count = clustersData?.clusters?.length ?? 0;
    countEl.textContent = String(count);

    const updated = clustersData?.generated_at ? new Date(clustersData.generated_at) : null;
    updatedEl.textContent = updated ? updated.toLocaleString() : "—";

    const baseUrl = getBaseUrl();
    const jsonUrl = baseUrl + "data/reported_locations.json";
    const csvUrl = baseUrl + "data/reported_locations.csv";

    if (jsonLink) jsonLink.href = jsonUrl;
    if (csvLink) csvLink.href = csvUrl;
    if (openLink) openLink.href = jsonUrl;
    
    // Setup poster report button
    const posterBtn = document.getElementById("download-poster");
    if (posterBtn) {
        posterBtn.addEventListener('click', generatePosterReport);
    }
}

// ============================================
// Poster-Style Report Generator
// ============================================

function generatePosterReport() {
    if (!clustersData || !timelineData) {
        alert("No data available to generate report");
        return;
    }
    
    const reportDate = new Date().toLocaleDateString('en-US', { 
        month: 'long', day: 'numeric', year: 'numeric' 
    });
    
    // Calculate statistics
    const totalSignals = clustersData.clusters?.reduce((sum, c) => sum + (c.size || 0), 0) || 0;
    const activeClusters = clustersData.clusters?.length || 0;
    const trend = timelineData.trend?.direction || 'stable';
    const trendMagnitude = timelineData.trend?.magnitude || 0;
    
    // Get top 5 clusters by strength
    const topClusters = (clustersData.clusters || [])
        .sort((a, b) => (b.strength || 0) - (a.strength || 0))
        .slice(0, 5);
    
    // Calculate ZIP breakdown
    const zipCounts = {};
    (clustersData.clusters || []).forEach(c => {
        const zip = String(c.zip).padStart(5, '0');
        zipCounts[zip] = (zipCounts[zip] || 0) + 1;
    });
    
    // Get top keywords
    const topKeywords = (keywordsData?.keywords || []).slice(0, 10);
    
    // Build printable HTML
    const reportHTML = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>HEAT Civic Signal Report - ${reportDate}</title>
    <style>
        @page { size: letter; margin: 0.75in; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            line-height: 1.6;
            color: #1a1a1a;
            max-width: 8.5in;
            margin: 0 auto;
            padding: 0;
        }
        .report-header {
            text-align: center;
            border-bottom: 3px solid #333;
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }
        h1 {
            font-size: 28pt;
            margin: 0.5rem 0;
            font-weight: 700;
        }
        .report-date {
            font-size: 14pt;
            color: #666;
            font-weight: 500;
        }
        .section {
            margin: 1.5rem 0;
            page-break-inside: avoid;
        }
        .section-title {
            font-size: 16pt;
            font-weight: 700;
            border-bottom: 2px solid #ddd;
            padding-bottom: 0.3rem;
            margin-bottom: 0.75rem;
        }
        .cluster-card {
            background: #f5f5f5;
            border-left: 4px solid #333;
            padding: 0.75rem;
            margin-bottom: 0.75rem;
        }
        .cluster-title {
            font-weight: 600;
            font-size: 12pt;
            margin-bottom: 0.3rem;
        }
        .cluster-meta {
            font-size: 10pt;
            color: #666;
            margin-bottom: 0.3rem;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
            margin: 1rem 0;
        }
        .stat-box {
            background: #f9f9f9;
            border: 2px solid #ddd;
            padding: 1rem;
            text-align: center;
        }
        .stat-value {
            font-size: 24pt;
            font-weight: 700;
            display: block;
            color: #333;
        }
        .stat-label {
            font-size: 10pt;
            color: #666;
            display: block;
            margin-top: 0.3rem;
        }
        .zip-list {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.5rem 0;
        }
        .zip-badge {
            background: #333;
            color: white;
            padding: 0.3rem 0.6rem;
            border-radius: 4px;
            font-size: 10pt;
            font-weight: 600;
        }
        .keyword-cloud {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 0.5rem 0;
        }
        .keyword-tag {
            background: #e9e9e9;
            padding: 0.3rem 0.6rem;
            border-radius: 4px;
            font-size: 10pt;
        }
        .footer {
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #ddd;
            font-size: 9pt;
            color: #666;
            text-align: center;
        }
        .sources-panel {
            background: #fcfcfc;
            border: 1px solid #ddd;
            padding: 0.75rem;
            margin: 0.5rem 0;
        }
        .source-item {
            font-size: 9pt;
            margin: 0.25rem 0;
        }
        @media print {
            body { padding: 0; }
            .no-print { display: none; }
        }
    </style>
</head>
<body>
    <div class="report-header">
        <h1>🔥 HEAT Civic Signal Report</h1>
        <div class="report-date">New Jersey — ${reportDate}</div>
    </div>
    
    <div class="section">
        <div class="section-title">📊 By the Numbers</div>
        <div class="stat-grid">
            <div class="stat-box">
                <span class="stat-value">${activeClusters}</span>
                <span class="stat-label">Active Report Groups</span>
            </div>
            <div class="stat-box">
                <span class="stat-value">${totalSignals}</span>
                <span class="stat-label">Total Signals</span>
            </div>
            <div class="stat-box">
                <span class="stat-value">${trend === 'increasing' ? '↑' : trend === 'decreasing' ? '↓' : '→'}</span>
                <span class="stat-label">Trend: ${trend} ${trendMagnitude > 0 ? '(+' + Math.round(trendMagnitude) + '%)' : ''}</span>
            </div>
            <div class="stat-box">
                <span class="stat-value">${Object.keys(zipCounts).length}</span>
                <span class="stat-label">ZIP Codes Affected</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <div class="section-title">📍 Location Summary</div>
        <div class="zip-list">
            ${Object.entries(zipCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([zip, count]) => `<span class="zip-badge">${zip}: ${count} reports</span>`)
                .join('')}
        </div>
    </div>
    
    <div class="section">
        <div class="section-title">💬 What Happened — Top 5 Report Groups</div>
        ${topClusters.map((cluster, idx) => `
            <div class="cluster-card">
                <div class="cluster-title">${idx + 1}. ${escapeHtml(cluster.summary || cluster.representative_text || 'No summary')}</div>
                <div class="cluster-meta">
                    📍 ZIP ${String(cluster.zip).padStart(5, '0')} • 
                    📊 ${cluster.size || 0} signals • 
                    💪 Strength: ${(cluster.strength || 0).toFixed(2)} •
                    📅 ${cluster.date_range || 'Recent'}
                </div>
                ${cluster.sources?.length ? `<div class="source-item">Sources: ${cluster.sources.slice(0, 3).join(', ')}</div>` : ''}
            </div>
        `).join('')}
    </div>
    
    <div class="section">
        <div class="section-title">🏷️ Top Keywords</div>
        <div class="keyword-cloud">
            ${topKeywords.map(kw => `<span class="keyword-tag">${escapeHtml(kw.word || kw)} ${kw.count ? '(' + kw.count + ')' : ''}</span>`).join('')}
        </div>
    </div>
    
    <div class="section">
        <div class="section-title">✅ How to Verify</div>
        <div class="sources-panel">
            <p><strong>All data comes from public sources:</strong></p>
            <ul>
                <li>Local news archives (NJ.com, TAPinto, News 12 NJ)</li>
                <li>NJ Attorney General press releases</li>
                <li>City council minutes (public records)</li>
                <li>Community advocacy reports</li>
                <li>Facebook community groups (opt-in)</li>
            </ul>
            <p style="margin-top: 0.5rem;"><strong>Original media links available in digital export files.</strong></p>
        </div>
    </div>
    
    <div class="footer">
        <p><strong>HEAT — They Are Here</strong> | Civic Signal Aggregation Tool</p>
        <p>This report shows aggregated patterns of civic attention from public records.</p>
        <p>NOT a real-time alert system. NOT individual sightings. ZIP-level geographic resolution only.</p>
        <p>Generated: ${new Date().toLocaleString()} | Data updated: ${clustersData.generated_at || 'Unknown'}</p>
    </div>
    
    <div class="no-print" style="text-align: center; margin: 2rem 0;">
        <button onclick="window.print()" style="padding: 1rem 2rem; font-size: 14pt; cursor: pointer;">
            🖨️ Print Report
        </button>
        <button onclick="window.close()" style="padding: 1rem 2rem; font-size: 14pt; cursor: pointer; margin-left: 1rem;">
            ✕ Close
        </button>
    </div>
</body>
</html>
    `.trim();
    
    // Open in new window
    const printWindow = window.open('', '_blank', 'width=900,height=1000');
    if (!printWindow) {
        alert('Please allow pop-ups to view the printable report');
        return;
    }
    
    printWindow.document.write(reportHTML);
    printWindow.document.close();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text || '');
    return div.innerHTML;
}

// ============================================
// Latest News & Alerts
// ============================================

function renderLatestNews() {
    const list = document.getElementById("latest-news-list");
    if (!list) return;
    
    const items = latestNewsData?.items || [];
    if (!items.length) {
        renderEmptyState(list, 'news');
        announceToScreenReader("No recent news available");
        return;
    }
    
    const limited = items.slice(0, 8);
    list.innerHTML = limited.map(item => {
        const timeAgo = getRelativeTime(item.timestamp);
        const source = item.source || "Multiple sources";
        const sourceType = item.source_type || item.sourceType || item.qualification || null;
        const sourceTypeLabel = sourceType ? escapeHtml(String(sourceType)) : "Vetted public / qualified community";
        const linkBlock = (item.urls?.length)
            ? `<div class="latest-news__links">${item.urls.slice(0,2).map(u => {
                    try {
                        const domain = new URL(u).hostname.replace('www.', '');
                        return `<a href="${u}" target="_blank" rel="noopener">${domain}</a>`;
                    } catch {
                        return '';
                    }
                }).join('')}</div>`
            : '';
        return `
            <article class="latest-news__item">
                <div class="latest-news__meta">
                    <span class="chip">ZIP ${item.zip}</span>
                    <span class="chip ${item.priority === 'high' ? 'chip-danger' : 'chip-muted'}">${item.priority === 'high' ? 'Priority' : 'Buffered'}</span>
                    <span class="latest-news__time">${timeAgo}</span>
                </div>
                <h3>${escapeHtml(item.headline || item.summary || 'Signal')}</h3>
                <p class="latest-news__summary">${escapeHtml(item.summary || '')}</p>
                <div class="latest-news__source">📰 ${escapeHtml(source)}</div>
                <div class="latest-news__source">🧾 Source type: ${sourceTypeLabel}</div>
                ${linkBlock}
            </article>
        `;
    }).join('');
    
    announceToScreenReader(`${limited.length} news reports loaded`);
}

function renderAlertsBanner(zipOverride = null) {
    const banner = document.getElementById("location-alert");
    const body = document.getElementById("location-alert-body");
    if (!banner || !body) return;
    
    const alertList = alertsData?.alerts || alertsData?.cluster_alerts || [];
    if (!alertList.length) {
        banner.classList.add("hidden");
        return;
    }
    
    const zip = zipOverride || getUserZip();
    
    // Find matching alert: ZIP match, "any" ZIP, or first alert
    let match = null;
    if (zip) {
        // Try to find ZIP-specific alert first
        match = alertList.find(a => String(a.zip).padStart(5, '0') === String(zip).padStart(5, '0'));
    }
    
    // Fall back to "any" alerts or first alert
    if (!match) {
        match = alertList.find(a => (a.zip || '').toLowerCase() === 'any') || alertList[0];
    }
    
    if (!match) {
        banner.classList.add("hidden");
        return;
    }
    
    const priorityLabel = match.priority === 'high' ? 'Priority' : match.type === 'pattern' ? 'Pattern' : 'Buffered';
    body.textContent = `${priorityLabel}: ${match.title} — ${match.body}`;
    banner.classList.remove("hidden");
}

function getUserZip() {
    const stored = localStorage.getItem("heat-user-zip");
    return stored ? String(stored).padStart(5, '0') : null;
}

// ============================================
// Cluster Cards
// ============================================

function renderClusters() {
    const container = document.getElementById("cluster-cards");
    const silenceWarning = document.getElementById("silence-warning");
    
    if (!clustersData || !clustersData.clusters || clustersData.clusters.length === 0) {
        renderEmptyState(container, 'clusters');
        announceToScreenReader("No active clusters in view");
        
        // Show silence warning when no clusters visible
        if (silenceWarning) {
            silenceWarning.classList.add("visible");
        }
        return;
    }
    
    // Hide silence warning when clusters are visible
    if (silenceWarning) {
        silenceWarning.classList.remove("visible");
    }
    
    announceToScreenReader(`${clustersData.clusters.length} clusters displayed`);
    
    // Sort clusters by most recent activity first
    const sortedClusters = [...clustersData.clusters].sort((a, b) => {
        const dateA = new Date(a.dateRange?.end || a.dateRange?.start || 0);
        const dateB = new Date(b.dateRange?.end || b.dateRange?.start || 0);
        return dateB - dateA; // Most recent first
    });
    
    const html = sortedClusters.map((cluster, index) => {
        const strengthClass = cluster.strength > 5 ? "high" : 
                             cluster.strength > 2 ? "medium" : "low";
        const strengthLabel = cluster.strength > 5 ? "High" : 
                             cluster.strength > 2 ? "Medium" : "Low";
        
        const dateRange = formatDateRange(cluster.dateRange.start, cluster.dateRange.end);
        const relativeTime = getRelativeTime(cluster.dateRange.end);
        const status = getSignalStatus(cluster.dateRange.end);
        const sources = Array.isArray(cluster.sources) ? cluster.sources.join(", ") : cluster.sources;
        
        // Check if this is recent activity (within last 48 hours)
        const endDate = new Date(cluster.dateRange.end);
        const now = new Date();
        const hoursSinceEnd = (now - endDate) / (1000 * 60 * 60);
        const isRecentActivity = hoursSinceEnd <= 48;
        const recentBadge = isRecentActivity ? '<span class="recent-badge" style="background: #ff4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; margin-left: 4px;">🔥 NEW</span>' : '';
        
        // Build media links section
        let mediaLinksHtml = '';
        if (cluster.mediaLinks?.length > 0) {
            const links = cluster.mediaLinks.slice(0, 3).map(url => {
                try {
                    const domain = new URL(url).hostname.replace('www.', '');
                    return `<a href="${url}" target="_blank" rel="noopener" class="media-link">🔗 ${domain}</a>`;
                } catch {
                    return '';
                }
            }).filter(Boolean).join('');
            mediaLinksHtml = `<div class="media-links">${links}</div>`;
        }
        
        return `
            <div class="cluster-card ${isRecentActivity ? 'recent-activity' : ''}" data-cluster-id="${cluster.id}" style="${isRecentActivity ? 'border-left: 4px solid #ff4444;' : ''}">
                <div class="header">
                    <span class="cluster-id">Cluster #${cluster.id}${recentBadge}</span>
                    <span class="strength ${strengthClass}">${strengthLabel}</span>
                    <span class="status-badge" style="background: ${status.color};">${status.icon} ${status.label}</span>
                </div>
                <p class="summary">${escapeHtml(cluster.summary)}</p>
                <div class="meta">
                    <span>📊 ${cluster.size} signals</span>
                    <span>📍 ZIP ${cluster.zip}</span>
                    <span>⏰ ${relativeTime}</span>
                    <span>📰 ${sources}</span>
                </div>
                <div class="date-info" style="font-size: 0.85em; color: var(--text-muted); margin-top: 8px;">
                    📅 ${dateRange}
                </div>
                ${mediaLinksHtml}
            </div>
        `;
    }).join("");
    
    container.innerHTML = html;
}

// ============================================
// Timeline Chart
// ============================================

function renderTimeline() {
    const ctx = document.getElementById("timeline-chart");

    if (!ctx) {
        console.error('Timeline chart canvas not found');
        return;
    }

    // Get weeks array (handle both old format and new format)
    const weeks = timelineData.weeks || timelineData || [];

    if (!weeks || weeks.length === 0) {
        if (ctx.parentElement) {
            ctx.parentElement.innerHTML = `
            <div class="no-data">
                <p>No timeline data available.</p>
            </div>
        `;
        }
        return;
    }
    
    // Update trend indicator
    const trend = timelineData.trend || {};
    const trendBadge = document.getElementById("trend-direction");
    if (trendBadge && trend.direction) {
        trendBadge.textContent = `📈 ${trend.direction} (${trend.change_pct > 0 ? '+' : ''}${trend.change_pct?.toFixed(0) || 0}%)`;
        trendBadge.className = `trend-badge ${trend.direction}`;
    }
    
    // Update burst indicator
    const burstBadge = document.getElementById("burst-indicator");
    if (burstBadge && timelineData.burst_score > 0.1) {
        burstBadge.classList.remove("hidden");
        burstBadge.textContent = `🔥 Burst Detected (${(timelineData.burst_score * 100).toFixed(0)}%)`;
    }
    
    // Sort by week
    const sortedData = [...weeks].sort((a, b) => a.week.localeCompare(b.week));
    
    // Format week labels
    const labels = sortedData.map(d => formatWeekLabel(d.week));
    const values = sortedData.map(d => d.count);
    
    // Create gradient
    const gradient = ctx.getContext("2d").createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, "rgba(248, 81, 73, 0.5)");
    gradient.addColorStop(0.5, "rgba(210, 153, 34, 0.3)");
    gradient.addColorStop(1, "rgba(63, 185, 80, 0.1)");
    
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Public signals",
                data: values,
                backgroundColor: gradient,
                borderColor: "rgba(88, 166, 255, 0.8)",
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false,
                },
                tooltip: {
                    backgroundColor: "#161b22",
                    titleColor: "#e6edf3",
                    bodyColor: "#8b949e",
                    borderColor: "#30363d",
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        title: (items) => `Week: ${items[0].label}`,
                        label: (item) => `${item.raw} public records`,
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: "rgba(48, 54, 61, 0.5)",
                    },
                    ticks: {
                        color: "#8b949e",
                        maxRotation: 45,
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: "rgba(48, 54, 61, 0.5)",
                    },
                    ticks: {
                        color: "#8b949e",
                        stepSize: 1,
                    }
                }
            }
        }
    });
}

// ============================================
// Utilities
// ============================================

function updateLastUpdated() {
    const el = document.getElementById("last-updated");
    const trendSummary = document.getElementById("trend-summary");
    const inlineSummaries = document.querySelectorAll(".trend-summary-inline");
    
    if (clustersData && clustersData.generated_at) {
        const date = new Date(clustersData.generated_at);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        let timeStr = '';
        if (diffMins < 60) {
            timeStr = `${diffMins}m ago`;
        } else if (diffHours < 24) {
            timeStr = `${diffHours}h ago`;
        } else {
            timeStr = `${diffDays}d ago`;
        }
        
        el.textContent = `${date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        })} (${timeStr})`;
    } else {
        el.textContent = new Date().toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    }
    
    // Update trend summary in header
    if (trendSummary && timelineData?.trend) {
        const trend = timelineData.trend;
        if (trend.direction === "increasing") {
            trendSummary.textContent = "is increasing";
            trendSummary.style.color = "var(--danger)";
        } else if (trend.direction === "decreasing") {
            trendSummary.textContent = "is decreasing";
            trendSummary.style.color = "var(--success)";
        } else {
            trendSummary.textContent = "is stable";
            trendSummary.style.color = "var(--accent)";
        }

        if (inlineSummaries?.length) {
            inlineSummaries.forEach(el => {
                el.textContent = trendSummary.textContent;
            });
        }
    }
}

function formatDateRange(start, end) {
    const startDate = new Date(start);
    const endDate = new Date(end);
    
    const opts = { month: "short", day: "numeric" };
    const startStr = startDate.toLocaleDateString("en-US", opts);
    const endStr = endDate.toLocaleDateString("en-US", { ...opts, year: "numeric" });
    
    return `${startStr} – ${endStr}`;
}

function getRelativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    
    if (diffDays > 30) {
        const months = Math.floor(diffDays / 30);
        return `${months} month${months > 1 ? 's' : ''} ago`;
    } else if (diffDays > 0) {
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else if (diffHours > 0) {
        return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffMinutes > 0) {
        return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
    } else {
        return 'Just now';
    }
}

function getSignalStatus(endDate) {
    const end = new Date(endDate);
    const now = new Date();
    const diffDays = Math.floor((now - end) / (1000 * 60 * 60 * 24));
    
    if (diffDays < 2) {
        return { label: 'ACTIVE', color: '#34a853', icon: '🟢' };
    } else if (diffDays < 7) {
        return { label: 'RECENT', color: '#fbbc04', icon: '🟡' };
    } else {
        return { label: 'PAST', color: '#9aa0a6', icon: '⚪' };
    }
}

function formatWeekLabel(weekStr) {
    // weekStr format: "2025-01-06/2025-01-12" or similar
    try {
        const startDate = weekStr.split("/")[0];
        const date = new Date(startDate);
        return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
        return weekStr;
    }
}

function truncate(str, maxLen) {
    if (!str) return "";
    if (str.length <= maxLen) return str;
    return str.substring(0, maxLen).trim() + "...";
}

// escapeHtml defined earlier — removed duplicate

// ============================================
// Quick Stats (This Week / Recent / Prior Week)
// ============================================

function updateQuickStats() {
    const todayEl = document.getElementById("stat-today");
    const yesterdayEl = document.getElementById("stat-yesterday");
    const last24hEl = document.getElementById("stat-24h");
    const last7dEl = document.getElementById("stat-7d");
    
    if (!todayEl || !yesterdayEl) return;
    
    const now = new Date();
    const sevenDaysAgo = new Date(now);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const fourteenDaysAgo = new Date(now);
    fourteenDaysAgo.setDate(fourteenDaysAgo.getDate() - 14);
    const threeDaysAgo = new Date(now);
    threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
    
    let recentCount = 0;       // Last 3 days ("Recent")
    let priorWeekCount = 0;    // 7-14 days ago ("Prior Week")
    let thisWeekCount = 0;     // Last 7 days ("This Week")
    let last7DaysCount = 0;    // Last 7 days ("Last 7d")
    
    // Count from clusters
    if (clustersData?.clusters) {
        clustersData.clusters.forEach(cluster => {
            const endDateTime = new Date(cluster.dateRange?.end);
            const size = cluster.size || 1;
            
            if (endDateTime >= threeDaysAgo) recentCount += size;
            if (endDateTime >= sevenDaysAgo) { thisWeekCount += size; last7DaysCount += size; }
            if (endDateTime >= fourteenDaysAgo && endDateTime < sevenDaysAgo) priorWeekCount += size;
        });
    }
    
    // Count from latest news
    if (latestNewsData?.items) {
        latestNewsData.items.forEach(item => {
            const itemDateTime = new Date(item.timestamp || item.date);
            
            if (itemDateTime >= threeDaysAgo) recentCount++;
            if (itemDateTime >= sevenDaysAgo) { thisWeekCount++; last7DaysCount++; }
            if (itemDateTime >= fourteenDaysAgo && itemDateTime < sevenDaysAgo) priorWeekCount++;
        });
    }
    
    todayEl.textContent = recentCount;
    yesterdayEl.textContent = priorWeekCount;
    if (last24hEl) last24hEl.textContent = thisWeekCount;
    if (last7dEl) last7dEl.textContent = last7DaysCount;
    
    // Color coding based on report level
    todayEl.style.color = recentCount > 5 ? 'var(--danger)' : recentCount > 2 ? 'var(--warning)' : 'var(--success)';
    yesterdayEl.style.color = priorWeekCount > 5 ? 'var(--danger)' : priorWeekCount > 2 ? 'var(--warning)' : 'var(--success)';
    if (last24hEl) last24hEl.style.color = thisWeekCount > 10 ? 'var(--danger)' : thisWeekCount > 5 ? 'var(--warning)' : 'var(--success)';
    if (last7dEl) last7dEl.style.color = last7DaysCount > 30 ? 'var(--danger)' : last7DaysCount > 15 ? 'var(--warning)' : 'var(--success)';
    
    // Update dashboard cards with recent report emphasis
    const dashClustersEl = document.getElementById('dash-clusters');
    if (dashClustersEl && thisWeekCount > 0) {
        dashClustersEl.title = `${thisWeekCount} this week, ${last7DaysCount} in last 7 days`;
    }
}

// ============================================
// Check Your Area ZIP Check
// ============================================

/**
 * Validate if a ZIP code is in New Jersey
 * NJ ZIP codes range from 07001-08989
 */
function isNewJerseyZip(zip) {
    const zipNum = parseInt(zip, 10);
    return (zipNum >= 7001 && zipNum <= 8989);
}

function initSafeCheck() {
    const toggleBtn = document.getElementById("safe-check-toggle");
    const panel = document.getElementById("safe-check-panel");
    const goBtn = document.getElementById("safe-check-go");
    const zipInput = document.getElementById("safe-check-zip");
    const resultDiv = document.getElementById("safe-check-result");
    
    if (!toggleBtn || !panel) return;
    
    toggleBtn.addEventListener("click", () => {
        panel.classList.toggle("hidden");
        toggleBtn.textContent = panel.classList.contains("hidden") ? "🛡️ Check Your Area" : "✕ Close";
    });
    
    goBtn?.addEventListener("click", () => checkZipSafety(zipInput?.value));
    zipInput?.addEventListener("keypress", (e) => {
        if (e.key === "Enter") checkZipSafety(zipInput.value);
    });
}

function checkZipSafety(zip) {
    const resultDiv = document.getElementById("safe-check-result");
    if (!resultDiv) return;
    
    // Clean and validate input
    const originalZip = String(zip || "").trim();
    zip = originalZip.padStart(5, '0');
    
    // Validate format
    if (!/^\d{5}$/.test(zip)) {
        resultDiv.innerHTML = '<p style="color: var(--warning);">⚠️ Please enter a valid 5-digit ZIP code.</p>';
        return;
    }
    
    // Check if it's a New Jersey ZIP
    if (!isNewJerseyZip(zip)) {
        resultDiv.innerHTML = `
            <p style="color: var(--info);">📍 ZIP ${zip} is outside New Jersey.</p>
            <p style="margin-top: 0.75rem; font-size: 0.85rem; color: var(--text-muted);">
                This tool currently covers New Jersey only. New Jersey ZIP codes range from 07001-08989.
            </p>
        `;
        return;
    }
    
    // Collect signals for this ZIP from the past 14 days
    const now = new Date();
    const cutoff = new Date(now);
    cutoff.setDate(cutoff.getDate() - 14);
    
    const signals = [];
    
    // From clusters
    if (clustersData?.clusters) {
        clustersData.clusters.forEach(cluster => {
            const clusterZip = String(cluster.zip).padStart(5, '0');
            if (clusterZip !== zip) return;
            
            const endDate = new Date(cluster.dateRange?.end);
            if (endDate >= cutoff) {
                signals.push({
                    date: cluster.dateRange?.end,
                    summary: cluster.summary || cluster.representative_text || 'ICE-related report group',
                    priority: cluster.strength > 5 ? 'high' : 'normal',
                    source: Array.isArray(cluster.sources) ? cluster.sources.join(', ') : cluster.sources,
                    type: 'cluster'
                });
            }
        });
    }
    
    // From latest news
    if (latestNewsData?.items) {
        latestNewsData.items.forEach(item => {
            const itemZip = String(item.zip).padStart(5, '0');
            if (itemZip !== zip) return;
            
            const itemDate = new Date(item.timestamp || item.date);
            if (itemDate >= cutoff) {
                signals.push({
                    date: item.timestamp || item.date,
                    summary: item.headline || item.summary || 'ICE-related report',
                    priority: item.priority === 'high' ? 'high' : 'normal',
                    source: item.source || 'Public source',
                    type: 'news'
                });
            }
        });
    }
    
    // Sort by date descending
    signals.sort((a, b) => new Date(b.date) - new Date(a.date));

    // Fly map to ZIP and update mobile panel immediately
    flyMapToZip(zip);
    updateMobileSafetyPanel(zip, signals);

    // Render results
    if (signals.length === 0) {
        resultDiv.innerHTML = `
            <div class="no-signals">
                ✅ No ICE-related reports in ZIP ${zip} for the past 14 days.
            </div>
            <p style="margin-top: 0.75rem; font-size: 0.85rem; color: var(--text-muted);">
                This is a valid New Jersey ZIP code. No reports have been recorded in this area recently.
            </p>
            <p style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--text-muted);">
                ⚠️ This does not guarantee safety. Data may be delayed or incomplete. Always verify independently and stay informed through community resources.
            </p>
        `;
        return;
    }
    
    const signalHtml = signals.slice(0, 10).map(sig => {
        const dateStr = new Date(sig.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        return `
            <div class="signal-item ${sig.priority === 'high' ? 'high-priority' : ''}">
                <div class="signal-date">${dateStr} • ${escapeHtml(sig.source)}</div>
                <div class="signal-summary">${escapeHtml(sig.summary)}</div>
            </div>
        `;
    }).join('');
    
    resultDiv.innerHTML = `
        <p style="margin-bottom: 0.75rem; font-weight: 600; color: var(--warning);">
            ⚠️ ${signals.length} signal(s) found in ZIP ${zip} (past 14 days)
        </p>
        ${signalHtml}
        ${signals.length > 10 ? `<p style="color: var(--text-muted); font-size: 0.85rem;">Showing 10 of ${signals.length} signals.</p>` : ''}
        <p style="margin-top: 0.75rem; font-size: 0.85rem; color: var(--text-muted);">
            This is interpretive data. Verify independently and consult community resources.
        </p>
    `;
}

// ============================================
// Keywords & NLP Display
// ============================================

const ZIP_NAMES = {
    "07060": "Plainfield",
    "07062": "Plainfield West",
    "07063": "Plainfield South",
    "08901": "New Brunswick",
    "08817": "Edison",
    "08854": "Piscataway",
    "08611": "Trenton"
};

let originalKeywords = null;

function renderKeywords(region = 'statewide') {
    const cloudContainer = document.getElementById("keyword-cloud");
    const lastUpdated = document.getElementById("keywords-last-updated");
    const categoryContainer = document.getElementById("category-distribution");

    if (!cloudContainer) {
        console.error('Keyword cloud container not found');
        return;
    }

    if (!keywordsData) {
        cloudContainer.innerHTML = '<p class="no-data">No keyword data available.</p>';
        return;
    }

    // Show last updated timestamp
    if (keywordsData.generated_at && lastUpdated) {
        const updated = new Date(keywordsData.generated_at);
        const hoursAgo = Math.floor((Date.now() - updated) / (1000 * 60 * 60));
        lastUpdated.textContent = `• Updated ${hoursAgo}h ago`;
    }
    
    // Use enriched keywords - always statewide (no static regional filtering)
    // Behavioral regions are emergent and dynamic, not static filters
    let keywords = keywordsData.keywords || [];
    
    if (keywords.length > 0) {
        // Sort keywords by recency (most recent first), then by count
        keywords.sort((a, b) => {
            const recencyA = a.recency_hours || 999999;
            const recencyB = b.recency_hours || 999999;
            // First sort by recency (lower hours = more recent = higher priority)
            if (Math.abs(recencyA - recencyB) > 24) {
                return recencyA - recencyB;
            }
            // If within same day, sort by count
            return (b.count || 0) - (a.count || 0);
        });
        
        const maxCount = Math.max(...keywords.map(k => k.count || 0));
        
        const keywordHtml = keywords.map(kw => {
            const count = kw.count || 0;
            const size = count / maxCount;
            let sizeClass = "";
            if (size > 0.7) sizeClass = "large";
            else if (size > 0.4) sizeClass = "medium";
            
            // Build location display for tooltip
            const topLocation = ZIP_NAMES[kw.top_location] || kw.top_location || "Unknown";
            const locationsText = kw.locations ? Object.entries(kw.locations)
                .map(([zip, cnt]) => `${ZIP_NAMES[zip] || zip}: ${cnt}`)
                .join(', ') : '';
            
            // Calculate recency indicator
            const hoursAgo = kw.recency_hours || 999999;
            const recencyClass = hoursAgo < 24 ? "recent" : hoursAgo < 72 ? "semi-recent" : "";
            
            const sources = kw.sources ? kw.sources.join(', ') : 'Unknown';
            
            // Compact display: word + count (location only on hover via CSS)
            return `
                <div class="keyword-tag-enhanced ${sizeClass} ${recencyClass}" 
                     title="${kw.word}: ${count} mentions\n📍 ${locationsText || topLocation}\n📰 Sources: ${sources}\n🕐 ${Math.floor(hoursAgo)}h ago">
                    <span class="keyword-word">${kw.word}</span>
                    <span class="keyword-count">${count}</span>
                    <span class="keyword-location">📍${topLocation}</span>
                </div>
            `;
        }).join("");
        
        cloudContainer.innerHTML = keywordHtml;
    } else {
        cloudContainer.innerHTML = '<p class="no-data">No keywords extracted yet.</p>';
    }
    
    // Render category distribution
    const categories = keywordsData.categories || {};
    if (Object.keys(categories).length > 0 && categoryContainer) {
        const categoryHtml = Object.entries(categories)
            .sort((a, b) => b[1] - a[1])
            .map(([name, count]) => `
                <div class="category-item">
                    <div class="name">${name}</div>
                    <div class="count">${count}</div>
                </div>
            `).join("");
        
        categoryContainer.innerHTML = categoryHtml;
    }
}

// Initialize keyword controls
function initKeywordControls() {
    // Randomize button handler
    const refreshBtn = document.getElementById("keyword-refresh");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", () => {
            if (keywordsData && keywordsData.keywords && keywordsData.keywords.length > 0) {
                // Save original if not saved
                if (!originalKeywords) {
                    originalKeywords = [...keywordsData.keywords];
                }
                
                // Shuffle and take random 10
                const shuffled = [...originalKeywords].sort(() => Math.random() - 0.5);
                keywordsData.keywords = shuffled.slice(0, 10);
                renderKeywords(currentRegion);
                
                // Restore after 5 seconds
                setTimeout(() => {
                    keywordsData.keywords = originalKeywords;
                    renderKeywords(currentRegion);
                }, 5000);
            }
        });
    }
    
    // Region display is now updated by region button clicks only
    // No separate keyword filter - keywords follow the header region selection
}

// ============================================
// 3D Map Mode (iPhone-style tilted view)
// ============================================

function init3DToggle() {
    const toggle3dBtn = document.getElementById("toggle3d");
    if (!toggle3dBtn) return;
    
    toggle3dBtn.addEventListener("click", () => {
        is3DMode = !is3DMode;
        
        if (is3DMode) {
            enable3DMode();
            toggle3dBtn.textContent = "Disable 3D";
            toggle3dBtn.style.background = "var(--accent)";
            toggle3dBtn.style.color = "#000";
        } else {
            disable3DMode();
            toggle3dBtn.textContent = "Enable 3D";
            toggle3dBtn.style.background = "var(--bg-darker)";
            toggle3dBtn.style.color = "var(--accent)";
        }
    });
}

function enable3DMode() {
    // Switch to satellite-style basemap
    map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) {
            map.removeLayer(layer);
        }
    });
    
    // Add hybrid satellite + labels layer
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
        attribution: "Esri, DigitalGlobe, GeoEye, Earthstar Geographics",
        maxZoom: 19,
    }).addTo(map);
    
    // Add labels overlay
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png", {
        subdomains: "abcd",
        maxZoom: 19,
        opacity: 0.7,
    }).addTo(map);
    
    // Increase zoom for "closer" feel
    map.setZoom(Math.min(map.getZoom() + 1, 17));
    
    // Enhance cluster markers with 3D effect
    clusterMarkers.forEach(marker => {
        marker.setStyle({
            weight: 3,
            opacity: 1,
            fillOpacity: 0.6,
            shadowSize: [30, 30],
        });
    });
    
    // Add pulsing animation
    const styleSheet = document.styleSheets[0];
    try {
        styleSheet.insertRule(`
            @keyframes pulse3d {
                0%, 100% { transform: scale(1); opacity: 0.6; }
                50% { transform: scale(1.15); opacity: 0.8; }
            }
        `, styleSheet.cssRules.length);
    } catch (e) {
        // Rule might already exist
    }
}

function disable3DMode() {
    // Switch back to dark basemap
    map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) {
            map.removeLayer(layer);
        }
    });
    
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: "abcd",
        maxZoom: 19,
    }).addTo(map);
    
    // Reset zoom
    map.setZoom(Math.max(map.getZoom() - 1, PLAINFIELD_ZOOM));
    
    // Reset marker styles
    clusterMarkers.forEach(marker => {
        marker.setStyle({
            weight: 2,
            opacity: 0.8,
            fillOpacity: 0.4,
        });
    });
}

// ============================================
// Event Tracking & Links
// ============================================

function initEventTracking() {
    // Track user interactions for analytics
    trackMapInteractions();
    trackClusterClicks();
    trackSubmissions();
}

function trackMapInteractions() {
    map.on("moveend", () => {
        const center = map.getCenter();
        const zoom = map.getZoom();
        logEvent("map_move", { lat: center.lat, lng: center.lng, zoom });
    });
    
    map.on("click", (e) => {
        logEvent("map_click", { lat: e.latlng.lat, lng: e.latlng.lng });
    });
}

function trackClusterClicks() {
    // Track when users click cluster cards
    document.addEventListener("click", (e) => {
        if (e.target.closest(".cluster-card")) {
            const card = e.target.closest(".cluster-card");
            const clusterId = card.dataset.clusterId;
            logEvent("cluster_card_click", { cluster_id: clusterId });
        }
    });
}

function trackSubmissions() {
    // Track submit button clicks
    const submitBtn = document.querySelector(".submit-signal-btn");
    if (submitBtn) {
        submitBtn.addEventListener("click", () => {
            logEvent("submit_button_click", { source: "mobile" });
        });
    }
}

function logEvent(eventName, data) {
    // Store events locally (in production, send to analytics service)
    const events = JSON.parse(localStorage.getItem("heat_events") || "[]");
    events.push({
        event: eventName,
        timestamp: new Date().toISOString(),
        data: data,
    });
    
    // Keep only last 100 events
    if (events.length > 100) {
        events.shift();
    }
    
    localStorage.setItem("heat_events", JSON.stringify(events));
    
    // Console log for development
    console.log(`[EVENT] ${eventName}:`, data);
}

// Export events as text for sharing
function exportEvents() {
    const events = JSON.parse(localStorage.getItem("heat_events") || "[]");
    
    let text = "HEAT — They Are Here — Event Log\n";
    text += "=".repeat(50) + "\n\n";
    
    events.forEach(event => {
        text += `[${new Date(event.timestamp).toLocaleString()}] ${event.event}\n`;
        text += `  ${JSON.stringify(event.data)}\n\n`;
    });
    
    return text;
}

// Make export function available globally
window.exportHeatEvents = exportEvents;

// ============================================
// Timeline Slider for Date Filtering
// ============================================

let allClustersData = null;  // Store original clusters for filtering

function initTimelineSlider() {
    const slider = document.getElementById("date-range-slider");
    const startLabel = document.getElementById("slider-start");
    const endLabel = document.getElementById("slider-end");
    const playBtn = document.getElementById("timeline-play-btn");
    
    if (!slider || !clustersData?.clusters?.length) return;
    
    // Store original data for filtering
    allClustersData = { ...clustersData };
    
    // Find date range from clusters
    const dates = clustersData.clusters.flatMap(c => [
        new Date(c.dateRange.start).getTime(),
        new Date(c.dateRange.end).getTime()
    ]);
    
    const minDate = Math.min(...dates);
    const maxDate = Math.max(...dates);
    
    slider.min = minDate;
    slider.max = maxDate;
    slider.value = maxDate;
    
    // Format labels
    const formatDate = (ts) => new Date(ts).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
    startLabel.textContent = formatDate(minDate);
    endLabel.textContent = formatDate(maxDate);
    
    // Slider change handler
    slider.addEventListener("input", () => {
        const cutoffDate = parseInt(slider.value);
        filterClustersByDate(cutoffDate);
    });
    
    // Play button for animation
    let isPlaying = false;
    let playInterval = null;
    
    playBtn?.addEventListener("click", () => {
        if (isPlaying) {
            clearInterval(playInterval);
            playBtn.textContent = "▶ Play";
            isPlaying = false;
        } else {
            slider.value = slider.min;
            filterClustersByDate(parseInt(slider.min));
            playBtn.textContent = "⏸ Pause";
            isPlaying = true;
            
            const step = (maxDate - minDate) / 50;  // 50 animation steps
            playInterval = setInterval(() => {
                const newVal = parseInt(slider.value) + step;
                if (newVal >= maxDate) {
                    slider.value = maxDate;
                    filterClustersByDate(maxDate);
                    clearInterval(playInterval);
                    playBtn.textContent = "▶ Play";
                    isPlaying = false;
                } else {
                    slider.value = newVal;
                    filterClustersByDate(newVal);
                }
            }, 100);
        }
    });
}

function filterClustersByDate(cutoffTimestamp) {
    if (!allClustersData?.clusters) return;
    
    // Filter clusters to those active before cutoff date
    const filtered = allClustersData.clusters.filter(c => {
        const startDate = new Date(c.dateRange.start).getTime();
        return startDate <= cutoffTimestamp;
    });
    
    // Update global data
    clustersData = { ...allClustersData, clusters: filtered };
    
    // Clear and re-render map markers
    map.eachLayer((layer) => {
        if (layer instanceof L.CircleMarker) {
            map.removeLayer(layer);
        }
    });
    
    clusterMarkers = [];
    renderMap();
    renderClusters();
    
    // Update current date display
    const currentLabel = document.getElementById("slider-current");
    if (currentLabel) {
        currentLabel.textContent = new Date(cutoffTimestamp).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }
}

// ============================================
// Heatmap Overlay Layer
// ============================================

let heatLayer = null;

function initHeatmapLayer() {
    const toggleBtn = document.getElementById("toggle-heatmap");
    if (!toggleBtn) return;
    
    toggleBtn.addEventListener("click", () => {
        if (heatLayer) {
            map.removeLayer(heatLayer);
            heatLayer = null;
            toggleBtn.textContent = "🔥 Show Heatmap";
            toggleBtn.classList.remove("active");
        } else {
            addHeatmapLayer();
            toggleBtn.textContent = "🔥 Hide Heatmap";
            toggleBtn.classList.add("active");
        }
    });
}

function addHeatmapLayer() {
    if (!clustersData?.clusters?.length) return;
    
    // Create heat data points from clusters
    const heatData = clustersData.clusters.map(cluster => {
        const zip5 = String(cluster.zip).padStart(5, '0');
        const coords = ZIP_COORDS[zip5] || ZIP_COORDS[cluster.zip] || PLAINFIELD_CENTER;
        
        // Weight by strength and size
        const intensity = Math.min((cluster.strength * cluster.size) / 10, 1);
        
        return [...coords, intensity];
    });
    
    // Create concentric ring overlays for each cluster
    clustersData.clusters.forEach(cluster => {
        const zip5 = String(cluster.zip).padStart(5, '0');
        const coords = ZIP_COORDS[zip5] || ZIP_COORDS[cluster.zip] || PLAINFIELD_CENTER;
        
        // Add graduated rings
        const rings = [
            { radius: 800, color: "#f85149", opacity: 0.15 },
            { radius: 500, color: "#d29922", opacity: 0.2 },
            { radius: 200, color: "#ff6b6b", opacity: 0.3 },
        ];
        
        rings.forEach(ring => {
            L.circle(coords, {
                radius: ring.radius * (cluster.strength / 3),
                color: ring.color,
                fillColor: ring.color,
                fillOpacity: ring.opacity,
                weight: 0,
                className: "heatmap-ring"
            }).addTo(map);
        });
    });
    
    heatLayer = true;  // Flag that heatmap is active
}

// ============================================
// Vulnerability Overlay Layer (Shift 7)
// ============================================

let vulnerabilityLayer = null;

function initVulnerabilityLayer() {
    const toggleBtn = document.getElementById("toggle-vulnerability");
    if (!toggleBtn) return;

    toggleBtn.addEventListener("click", () => {
        if (vulnerabilityLayer) {
            map.removeLayer(vulnerabilityLayer);
            vulnerabilityLayer = null;
            toggleBtn.textContent = "Vulnerability";
            toggleBtn.classList.remove("active");
        } else {
            loadVulnerabilityOverlay();
            toggleBtn.textContent = "Hide Vulnerability";
            toggleBtn.classList.add("active");
        }
    });
}

function loadVulnerabilityOverlay() {
    fetch("data/vulnerability.geojson")
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .then(geojson => {
            if (!geojson || !geojson.features) {
                console.warn("Vulnerability GeoJSON not available");
                return;
            }
            // Color by vulnerability_index (0=green, 100=red)
            vulnerabilityLayer = L.geoJSON(geojson, {
                style: function (feature) {
                    const idx = feature.properties.vulnerability_index || 0;
                    return {
                        fillColor: _vulnColor(idx),
                        fillOpacity: 0.35,
                        weight: 1.5,
                        color: "#444",
                        opacity: 0.6,
                    };
                },
                onEachFeature: function (feature, layer) {
                    const p = feature.properties;
                    const popup = `
                        <strong>ZIP ${p.zip}</strong> — ${p.name || ''}<br>
                        Vulnerability Index: <strong>${p.vulnerability_index}</strong> (${p.category})<br>
                        <small>
                        Median Income: $${(p.median_income || 0).toLocaleString()}<br>
                        Linguistic Isolation: ${p.linguistic_isolation_pct}%<br>
                        Foreign Born: ${p.foreign_born_pct}%<br>
                        Renter: ${p.renter_pct}%<br>
                        No Vehicle: ${p.no_vehicle_pct}%
                        </small>`;
                    layer.bindPopup(popup);
                },
            }).addTo(map);
        });
}

function _vulnColor(index) {
    // 0 → green, 50 → yellow, 100 → red
    if (index < 20) return "#2d7d46";
    if (index < 40) return "#81c995";
    if (index < 60) return "#f9ab00";
    if (index < 80) return "#ee675c";
    return "#c62828";
}


// ============================================
// KDE Density Heatmap Layer (GeoJSON polygons)
// ============================================

let kdeLayer = null;

function initKDELayer() {
    const toggleBtn = document.getElementById("toggle-kde");
    if (!toggleBtn) return;

    toggleBtn.addEventListener("click", () => {
        if (kdeLayer) {
            map.removeLayer(kdeLayer);
            kdeLayer = null;
            toggleBtn.textContent = "Density";
            toggleBtn.classList.remove("active");
        } else {
            loadKDELayer();
            toggleBtn.textContent = "Hide Density";
            toggleBtn.classList.add("active");
        }
    });
}

function loadKDELayer() {
    fetch("data/heatmap.geojson")
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .then(geojson => {
            if (!geojson || !geojson.features || !geojson.features.length) {
                console.warn("KDE heatmap GeoJSON not available");
                return;
            }

            // Find max density for normalization
            const maxDensity = Math.max(
                ...geojson.features.map(f => f.properties.density || 0),
                0.001
            );

            kdeLayer = L.geoJSON(geojson, {
                style: function (feature) {
                    const d = (feature.properties.density || 0) / maxDensity;
                    return {
                        fillColor: _kdeDensityColor(d),
                        fillOpacity: Math.max(0.05, d * 0.6),
                        weight: 0,
                        color: "transparent",
                        className: "kde-cell",
                    };
                },
                onEachFeature: function (feature, layer) {
                    const p = feature.properties;
                    layer.bindTooltip(
                        `Density: ${(p.density || 0).toFixed(4)}`,
                        { sticky: true, opacity: 0.85 }
                    );
                },
                filter: function (feature) {
                    // Only show cells with meaningful density (top 60%)
                    return (feature.properties.density || 0) > 0;
                },
            }).addTo(map);
        });
}

function _kdeDensityColor(normalized) {
    // 0 → cool blue, 0.5 → warm yellow, 1.0 → hot red
    if (normalized < 0.15) return "#1a237e";
    if (normalized < 0.30) return "#0d47a1";
    if (normalized < 0.45) return "#00838f";
    if (normalized < 0.60) return "#558b2f";
    if (normalized < 0.75) return "#f9a825";
    if (normalized < 0.90) return "#ef6c00";
    return "#c62828";
}

// ============================================
// Hotspot Zones Layer (Getis-Ord Gi* points)
// ============================================

let hotspotsLayer = null;

function initHotspotsLayer() {
    const toggleBtn = document.getElementById("toggle-hotspots");
    if (!toggleBtn) return;

    toggleBtn.addEventListener("click", () => {
        if (hotspotsLayer) {
            map.removeLayer(hotspotsLayer);
            hotspotsLayer = null;
            toggleBtn.textContent = "Hotspots";
            toggleBtn.classList.remove("active");
        } else {
            loadHotspotsLayer();
            toggleBtn.textContent = "Hide Hotspots";
            toggleBtn.classList.add("active");
        }
    });
}

function loadHotspotsLayer() {
    fetch("data/hotspots.geojson")
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .then(geojson => {
            if (!geojson || !geojson.features || !geojson.features.length) {
                console.warn("Hotspots GeoJSON not available");
                return;
            }

            hotspotsLayer = L.geoJSON(geojson, {
                pointToLayer: function (feature, latlng) {
                    const p = feature.properties;
                    const zscore = Math.abs(p.gi_zscore || 0);
                    const isHot = p.is_hotspot === true;
                    const radius = Math.max(300, zscore * 600);

                    return L.circle(latlng, {
                        radius: radius,
                        color: isHot ? "#ff1744" : "#448aff",
                        fillColor: isHot ? "#ff1744" : "#448aff",
                        fillOpacity: 0.2,
                        weight: 2,
                        opacity: 0.7,
                        className: "hotspot-zone",
                    });
                },
                onEachFeature: function (feature, layer) {
                    const p = feature.properties;
                    const type = p.is_hotspot ? "🔥 Hotspot" : "❄️ Coldspot";
                    const popup = `
                        <strong>${type}</strong> — ZIP ${p.zip}<br>
                        Gi* z-score: <strong>${(p.gi_zscore || 0).toFixed(3)}</strong><br>
                        p-value: ${(p.gi_pvalue || 0).toFixed(4)}<br>
                        <small>Cluster #${p.cluster_id} · Weight: ${(p.weight || 0).toFixed(3)}</small>`;
                    layer.bindPopup(popup);
                },
            }).addTo(map);
        });
}

// ============================================
// Spatial Cluster Centroids Layer
// ============================================

let spatialClustersLayer = null;

function initSpatialClustersLayer() {
    const toggleBtn = document.getElementById("toggle-clusters-geo");
    if (!toggleBtn) return;

    toggleBtn.addEventListener("click", () => {
        if (spatialClustersLayer) {
            map.removeLayer(spatialClustersLayer);
            spatialClustersLayer = null;
            toggleBtn.textContent = "Clusters";
            toggleBtn.classList.remove("active");
        } else {
            loadSpatialClustersLayer();
            toggleBtn.textContent = "Hide Clusters";
            toggleBtn.classList.add("active");
        }
    });
}

function loadSpatialClustersLayer() {
    fetch("data/spatial_clusters.geojson")
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .then(geojson => {
            if (!geojson || !geojson.features || !geojson.features.length) {
                console.warn("Spatial clusters GeoJSON not available");
                return;
            }

            // Find max weight for sizing
            const maxWeight = Math.max(
                ...geojson.features.map(f => f.properties.weight || 0),
                0.01
            );

            spatialClustersLayer = L.geoJSON(geojson, {
                pointToLayer: function (feature, latlng) {
                    const p = feature.properties;
                    const normWeight = (p.weight || 0) / maxWeight;
                    const radius = 5 + normWeight * 12;

                    // Color by spatial_cluster_id (distinct colors per group)
                    const clusterColors = [
                        "#e91e63", "#00bcd4", "#ff9800", "#4caf50",
                        "#9c27b0", "#03a9f4", "#ff5722", "#8bc34a",
                        "#673ab7", "#009688", "#ffc107", "#2196f3",
                    ];
                    const color = clusterColors[(p.spatial_cluster_id || 0) % clusterColors.length];

                    return L.circleMarker(latlng, {
                        radius: radius,
                        color: color,
                        fillColor: color,
                        fillOpacity: 0.6,
                        weight: 2,
                        opacity: 0.9,
                        className: "spatial-cluster-marker",
                    });
                },
                onEachFeature: function (feature, layer) {
                    const p = feature.properties;
                    const popup = `
                        <strong>Spatial Cluster #${p.spatial_cluster_id}</strong><br>
                        ZIP: ${p.zip}<br>
                        Signal Cluster: #${p.cluster_id}<br>
                        Weight: ${(p.weight || 0).toFixed(4)}<br>
                        <small>${p.timestamp || ''}</small>`;
                    layer.bindPopup(popup);
                },
            }).addTo(map);
        });
}

// ============================================
// Propagation Waves Layer
// ============================================

let propagationLayer = null;

function initPropagationLayer() {
    const toggleBtn = document.getElementById("toggle-propagation");
    if (!toggleBtn) return;

    toggleBtn.addEventListener("click", () => {
        if (propagationLayer) {
            map.removeLayer(propagationLayer);
            propagationLayer = null;
            toggleBtn.textContent = "Waves";
            toggleBtn.classList.remove("active");
        } else {
            loadPropagationLayer();
            toggleBtn.textContent = "Hide Waves";
            toggleBtn.classList.add("active");
        }
    });
}

function loadPropagationLayer() {
    fetch("data/propagation_waves.geojson")
        .then(r => r.ok ? r.json() : null)
        .catch(() => null)
        .then(geojson => {
            if (!geojson || !geojson.features || !geojson.features.length) {
                console.warn("Propagation waves GeoJSON not available or empty");
                // Disable button if no data
                const toggleBtn = document.getElementById("toggle-propagation");
                if (toggleBtn) {
                    toggleBtn.classList.remove("active");
                    toggleBtn.textContent = "Waves (none)";
                    toggleBtn.disabled = true;
                    toggleBtn.style.opacity = "0.5";
                }
                propagationLayer = null;
                return;
            }

            propagationLayer = L.geoJSON(geojson, {
                style: function (feature) {
                    const p = feature.properties;
                    const speed = p.speed_kmph || 1;
                    const weight = Math.max(2, Math.min(6, speed / 5));
                    return {
                        color: "#7c4dff",
                        weight: weight,
                        opacity: 0.7,
                        dashArray: "12 6",
                        className: "propagation-wave",
                    };
                },
                onEachFeature: function (feature, layer) {
                    const p = feature.properties;
                    const popup = `
                        <strong>Propagation Vector</strong><br>
                        ${p.origin_zip || '?'} → ${p.dest_zip || '?'}<br>
                        Topic: ${p.topic || 'Unknown'}<br>
                        Speed: ${(p.speed_kmph || 0).toFixed(1)} km/h<br>
                        Delay: ${(p.delay_hours || 0).toFixed(1)} hours`;
                    layer.bindPopup(popup);
                },
                pointToLayer: function (feature, latlng) {
                    // Arrow markers at destination points
                    return L.circleMarker(latlng, {
                        radius: 4,
                        color: "#7c4dff",
                        fillColor: "#b388ff",
                        fillOpacity: 0.8,
                        weight: 2,
                    });
                },
            }).addTo(map);
        });
}

// ============================================
// Stability Visualization Mode (Shift 9)
// ============================================

let stabilityMode = false;

function initStabilityMode() {
    const toggleBtn = document.getElementById("toggle-stability");
    if (!toggleBtn) return;

    // Restore saved preference
    stabilityMode = localStorage.getItem("heat-stability-mode") === "true";
    if (stabilityMode) _activateStability(toggleBtn);

    toggleBtn.addEventListener("click", () => {
        stabilityMode = !stabilityMode;
        localStorage.setItem("heat-stability-mode", String(stabilityMode));
        if (stabilityMode) {
            _activateStability(toggleBtn);
        } else {
            _deactivateStability(toggleBtn);
        }
    });
}

function _activateStability(btn) {
    document.body.classList.add("stability-mode");
    btn.textContent = "Exit Stability";
    btn.classList.add("active");

    // Replace "heat level" text with "engagement level"
    document.querySelectorAll(".heat-level-label").forEach(el => {
        el.dataset.originalText = el.textContent;
        el.textContent = el.textContent
            .replace(/heat level/gi, "Engagement Level")
            .replace(/heat/gi, "Engagement");
    });

    // Refresh map markers with stability colours
    if (typeof renderMap === "function") renderMap();
    if (typeof renderClusters === "function") renderClusters();

    // Surface silence context as "monitored calm"
    _showStabilityCalm();
}

function _deactivateStability(btn) {
    document.body.classList.remove("stability-mode");
    btn.textContent = "Stability";
    btn.classList.remove("active");

    // Restore original text
    document.querySelectorAll(".heat-level-label").forEach(el => {
        if (el.dataset.originalText) el.textContent = el.dataset.originalText;
    });

    _hideStabilityCalm();

    if (typeof renderMap === "function") renderMap();
    if (typeof renderClusters === "function") renderClusters();
}

/**
 * Show silence_context data from clusters.json as "monitored calm" cards.
 */
function _showStabilityCalm() {
    let container = document.getElementById("stability-calm-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "stability-calm-container";
        container.className = "stability-calm-container";
        const mapSection = document.getElementById("map-section");
        if (mapSection) mapSection.appendChild(container);
    }

    const silence = clustersData?.silence_context;
    if (!silence || Object.keys(silence).length === 0) {
        container.innerHTML = `
            <div class="stability-calm-card">
                <span class="calm-icon">🟢</span>
                <span class="calm-text">All monitored areas currently show civic engagement signals.</span>
            </div>`;
        return;
    }

    container.innerHTML = Object.entries(silence).map(([zip, ctx]) => {
        const msg = typeof ctx === "string" ? ctx : (ctx.message || ctx.context || "Monitored calm — no reports ≠ nothing happening.");
        // Compute trend indicator
        const trend = _getStabilityTrend(zip);
        const trendIcon = trend === "improving" ? "📈" : trend === "declining" ? "📉" : "➡️";
        return `
            <div class="stability-calm-card" data-zip="${zip}">
                <span class="calm-icon">🟢</span>
                <div class="calm-body">
                    <strong>ZIP ${zip} — Monitored Calm</strong>
                    <p>${msg}</p>
                    <span class="stability-trend" title="Stability trend: ${trend}">${trendIcon} ${trend}</span>
                </div>
            </div>`;
    }).join("");
}

function _hideStabilityCalm() {
    const container = document.getElementById("stability-calm-container");
    if (container) container.innerHTML = "";
}

/**
 * Determine stability trend for a ZIP based on rolling cluster count.
 */
function _getStabilityTrend(zip) {
    if (!clustersData?.clusters) return "steady";
    const now = new Date();
    const clForZip = clustersData.clusters.filter(c => String(c.zip).padStart(5, "0") === zip);
    const recent = clForZip.filter(c => {
        const d = new Date(c.dateRange?.end || c.dateRange?.start);
        return (now - d) / 3600000 < 168; // last 7 days
    });
    const older = clForZip.filter(c => {
        const d = new Date(c.dateRange?.end || c.dateRange?.start);
        const h = (now - d) / 3600000;
        return h >= 168 && h < 336; // 7-14 days ago
    });
    if (recent.length < older.length) return "improving";
    if (recent.length > older.length) return "declining";
    return "steady";
}

/**
 * Get marker colour adapting to stability mode.
 * In stability mode: green = high engagement, blue = calm; no red.
 */
function getStabilityColor(strength) {
    if (!stabilityMode) return null; // use default colours
    if (strength > 5) return "#2d7d46";  // green — active civic engagement
    if (strength > 2) return "#4a90d9";  // blue — moderate
    return "#6eb5ff";                     // light blue — calm/stable
}


// ============================================
// WebSocket Real-Time Layer (Shift 13)
// ============================================

function initWebSocket() {
    if (typeof HeatWebSocket === "undefined") {
        console.log("WebSocket client not loaded — skipping real-time layer.");
        return;
    }

    // Determine tier from local storage or default to 0
    const tier = parseInt(localStorage.getItem("heat-tier") || "0", 10);
    const wsUrl = localStorage.getItem("heat-ws-url") || "ws://localhost:8765";

    HeatWebSocket.connect({
        url: wsUrl,
        tier: tier,
        subscriptions: ["cluster_update", "heatmap_refresh", "alert", "pipeline_status"],
    });

    // cluster_update → refresh map markers
    HeatWebSocket.on("cluster_update", function (data) {
        console.log("[WS] cluster_update received");
        if (data && data.clusters && typeof loadData === "function") {
            loadData().then(() => {
                if (typeof renderMap === "function") renderMap();
                if (typeof renderClusters === "function") renderClusters();
            });
        }
    });

    // heatmap_refresh → reload heatmap layer if visible
    HeatWebSocket.on("heatmap_refresh", function (data) {
        console.log("[WS] heatmap_refresh received");
        if (heatLayer) {
            // Remove existing, then re-add
            addHeatmapLayer();
        }
    });

    // alert → show toast notification
    HeatWebSocket.on("alert", function (data) {
        console.log("[WS] alert received:", data);
        // Toast is handled by websocket-client.js internally
    });

    // pipeline_status → update dashboard status indicator
    HeatWebSocket.on("pipeline_status", function (data) {
        console.log("[WS] pipeline_status:", data.status || data.stage);
        const indicator = document.getElementById("pipeline-status-indicator");
        if (indicator) {
            const status = data.status || "unknown";
            indicator.textContent = status === "pipeline_complete" ? "✅ Pipeline OK" : "🔄 " + status;
            indicator.classList.toggle("pipeline-ok", status === "pipeline_complete");
        }
    });

    console.log("WebSocket real-time layer initialized (tier " + tier + ")");
}


// ============================================
// Region Navigation
// ============================================

function setupRegionNavigation() {
    const regionButtons = document.querySelectorAll('.region-btn');
    
    regionButtons.forEach(button => {
        button.addEventListener('click', () => {
            const region = button.dataset.region;
            const regionData = REGIONS[region];
            
            if (!regionData) return;
            
            // Update active state
            regionButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Update current region and re-render keywords
            currentRegion = region;
            renderKeywords(region);
            
            // Update keyword region display text
            const regionDisplayText = document.getElementById('keyword-current-region');
            if (regionDisplayText) {
                const regionNames = {
                    'statewide': 'Statewide',
                    'north': 'North Jersey',
                    'central': 'Central Jersey',
                    'south': 'South Jersey'
                };
                regionDisplayText.textContent = regionNames[region] || 'Statewide';
            }
            
            // Fly to region with smooth animation
            map.flyTo(regionData.center, regionData.zoom, {
                duration: 1.2,
                easeLinearity: 0.25
            });
            
            // Update subtitle with region context
            const subtitle = document.querySelector('.subtitle');
            if (subtitle) {
                const originalText = subtitle.textContent;
                subtitle.textContent = `${regionData.name} — ${regionData.coverage}`;
                
                // Restore after 5 seconds
                setTimeout(() => {
                    subtitle.textContent = originalText;
                }, 5000);
            }
        });
    });
}

// ============================================
// Analytics Panel Integration
// ============================================

/**
 * Initialize analytics system with data context
 */
function initializeAnalytics() {
    if (!window.analyticsPanel || !window.filterEngine) {
        console.warn('Analytics components not loaded');
        return;
    }

    // Initialize FilterEngine with cluster data
    if (clustersData && Array.isArray(clustersData.clusters)) {
        window.filterEngine.initialize(clustersData.clusters, { keepFilters: false });
    }

    // Set data context for analytics panel
    window.analyticsPanel.setDataContext({
        timeline: timelineData,
        keywords: keywordsData,
        latestNews: latestNewsData,
        alerts: alertsData
    });

    // Set filter change handler to update map
    window.analyticsPanel.setFilterChangeHandler(function(filteredClusters, state, meta) {
        // Update map markers with filtered data
        if (map && filteredClusters) {
            updateMapMarkers(filteredClusters);
        }
        
        // Update dashboard stats with filtered data
        if (filteredClusters) {
            updateDashboardWithFiltered(filteredClusters);
        }
    });

    // Initialize the panel UI
    window.analyticsPanel.init();
}

/**
 * Update map markers with filtered cluster data
 */
function updateMapMarkers(clusters) {
    if (!map) return;
    
    // Clear existing markers
    if (window.clusterMarkers) {
        window.clusterMarkers.forEach(marker => map.removeLayer(marker));
    }
    window.clusterMarkers = [];

    // Add markers for filtered clusters
    clusters.forEach(cluster => {
        const marker = addClusterMarker(cluster);
        if (marker) window.clusterMarkers.push(marker);
    });

    // Update cluster bounds
    if (clusters.length > 0) {
        const bounds = L.latLngBounds(clusters.map(c => getClusterCoordinates(c)));
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
    }
}

/**
 * Update dashboard with filtered statistics
 */
function updateDashboardWithFiltered(clusters) {
    if (!window.statsCalculator) return;
    
    const summary = window.statsCalculator.clusterSummary(clusters);
    
    // Update dashboard cards
    const dashClusters = document.getElementById('dash-clusters');
    if (dashClusters) dashClusters.textContent = summary.totalClusters;
    
    const dashKeywords = document.getElementById('dash-keywords');
    if (dashKeywords) dashKeywords.textContent = summary.uniqueZips;
    
    // Update intensity
    const intensityFill = document.getElementById('intensity-fill');
    const dashIntensity = document.getElementById('dash-intensity');
    if (intensityFill && dashIntensity && summary.averageStrength) {
        const percent = Math.min((summary.averageStrength / 10) * 100, 100);
        intensityFill.style.width = percent + '%';
        dashIntensity.textContent = summary.averageStrength.toFixed(1);
    }
}

// NOTE: initAnalyticsIntegration() already exists at line 412
// It's called from DOMContentLoaded (line 1693) and loadData() (line 2401)

// ============================================
// Mobile Full-Screen Panel
// ============================================

/**
 * Fly the map to a ZIP code (reusable helper)
 */
function flyMapToZip(zip) {
    if (!map) return;
    const zipData = ZIP_BOUNDARIES[zip];
    if (zipData) {
        map.flyTo(zipData.center, 14, { duration: 0.8 });
    } else if (ZIP_COORDS[zip]) {
        map.flyTo(ZIP_COORDS[zip], 13, { duration: 0.8 });
    } else if (isNewJerseyZip(zip)) {
        map.flyTo(DEFAULT_CENTER, 10, { duration: 0.8 });
    }
}

/**
 * Update the mobile bottom sheet with danger level + signals for a ZIP
 */
function updateMobileSafetyPanel(zip, signals) {
    const panel = document.getElementById('mobile-panel');
    const safetyPane = document.getElementById('mpanel-safety');
    if (!panel || !safetyPane) return;

    let badgeClass, emoji, heading, subtext;
    if (signals.length === 0) {
        badgeClass = 'level-clear';
        emoji = '✅';
        heading = 'No Recent Reports';
        subtext = `ZIP ${zip} — No signals in past 14 days`;
    } else if (signals.length <= 2) {
        badgeClass = 'level-active';
        emoji = '⚠️';
        heading = 'Some Reports';
        subtext = `ZIP ${zip} — ${signals.length} signal(s) in past 14 days`;
    } else {
        badgeClass = 'level-elevated';
        emoji = '🔴';
        heading = 'Elevated Discussion';
        subtext = `ZIP ${zip} — ${signals.length} signals in past 14 days`;
    }

    const signalHtml = signals.slice(0, 5).map(sig => {
        const dateStr = new Date(sig.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return `<div class="mobile-signal-item">
            <div class="msi-date">${dateStr} · ${escapeHtml(sig.source)}</div>
            <div class="msi-text ${sig.priority === 'high' ? 'high-priority' : ''}">${escapeHtml(sig.summary)}</div>
        </div>`;
    }).join('');

    const moreHtml = signals.length > 5
        ? `<p style="color:var(--text-muted);font-size:0.78rem;margin-top:0.5rem;">+${signals.length - 5} more signals</p>`
        : '';

    safetyPane.innerHTML = `
        <div class="mobile-danger-badge ${badgeClass}">
            <div class="mdb-emoji">${emoji}</div>
            <div class="mdb-info">
                <h3>${heading}</h3>
                <p>${subtext}</p>
            </div>
        </div>
        ${signalHtml}
        ${moreHtml}
        <p style="font-size:0.72rem;color:var(--text-muted);margin-top:0.625rem;">Always verify independently. 72-hour delay active.</p>
    `;

    panel.classList.add('expanded');
    activateMobileTab('safety');
}

/**
 * Switch the active tab in the mobile bottom panel
 */
function activateMobileTab(tabName) {
    const panel = document.getElementById('mobile-panel');
    if (!panel) return;
    panel.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    panel.querySelectorAll('.mpanel').forEach(p => p.classList.toggle('active', p.id === `mpanel-${tabName}`));
}

/**
 * Wire up the mobile ZIP bar and panel interactions
 */
function initMobilePanel() {
    const panel    = document.getElementById('mobile-panel');
    const zipInput = document.getElementById('mobile-zip-input');
    const zipGo    = document.getElementById('mobile-zip-go');
    const handle   = document.getElementById('mobile-panel-handle');
    if (!panel) return;

    const doCheck = () => {
        const zip = (zipInput?.value || '').trim();
        if (zip) checkZipSafety(zip);
    };

    zipGo?.addEventListener('click', doCheck);
    zipInput?.addEventListener('keypress', e => { if (e.key === 'Enter') doCheck(); });
    zipInput?.addEventListener('input', e => {
        // Auto-trigger when 5 digits entered
        if (e.target.value.length === 5) doCheck();
    });

    // Drag handle toggles expanded state
    handle?.addEventListener('click', () => panel.classList.toggle('expanded'));

    // Tab switching
    panel.querySelectorAll('.panel-tab').forEach(tab => {
        tab.addEventListener('click', () => activateMobileTab(tab.dataset.tab));
    });
}

/**
 * Populate the mobile feed tab with latest news items
 */
function populateMobileFeed() {
    const feedEl = document.getElementById('mobile-feed-items');
    if (!feedEl) return;
    const items = latestNewsData?.items || [];
    if (items.length === 0) {
        feedEl.innerHTML = '<p style="color:var(--text-muted);font-size:0.85rem;">No recent reports available.</p>';
        return;
    }
    feedEl.innerHTML = items.slice(0, 15).map(item => {
        const dateStr = new Date(item.timestamp || item.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return `<div class="mfi-item">
            <div class="mfi-source">${dateStr} · ${escapeHtml(item.source || 'Source')} · ZIP ${escapeHtml(String(item.zip || '--'))}</div>
            <div class="mfi-headline">${escapeHtml(item.headline || item.summary || 'Report noted')}</div>
        </div>`;
    }).join('');
}
