/**
 * HEAT — Civic Signal Map
 * Static frontend for aggregated public attention patterns
 */

// Plainfield, NJ coordinates
const PLAINFIELD_CENTER = [40.6137, -74.4154];
const PLAINFIELD_ZOOM = 13;

// ZIP code approximate centers for Plainfield area
const ZIP_COORDS = {
    "07060": [40.6137, -74.4154],  // Central Plainfield
    "07062": [40.6280, -74.4050],  // North Plainfield area
    "07063": [40.5980, -74.4280],  // South Plainfield area
};

// Globals
let map;
let clustersData = null;
let timelineData = null;
let keywordsData = null;
let is3DMode = false;
let clusterMarkers = [];

// ============================================
// Initialization
// ============================================

document.addEventListener("DOMContentLoaded", async () => {
    initThemeToggle();
    initMap();
    await loadData();
    renderMap();
    renderClusters();
    renderTimeline();
    renderKeywords();
    updateLastUpdated();
    updateDashboard();
    init3DToggle();
    initEventTracking();
    initTimelineSlider();
    initHeatmapLayer();
    initDashboardClicks();
    initGeolocation();
});

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
    }
}

function detectZipFromCoords(lat, lng) {
    // Simple proximity check to Plainfield ZIPs
    const zips = [
        { zip: "07060", lat: 40.6137, lng: -74.4154 },
        { zip: "07062", lat: 40.6280, lng: -74.4050 },
        { zip: "07063", lat: 40.5980, lng: -74.4280 },
    ];
    
    let closest = null;
    let minDist = Infinity;
    
    zips.forEach(z => {
        const dist = Math.sqrt(Math.pow(lat - z.lat, 2) + Math.pow(lng - z.lng, 2));
        if (dist < minDist && dist < 0.05) { // Within ~3.5 miles
            minDist = dist;
            closest = z.zip;
        }
    });
    
    return closest;
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
    const keywordCount = keywordsData?.top_keywords?.length || 0;
    
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
        center: PLAINFIELD_CENTER,
        zoom: PLAINFIELD_ZOOM,
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
    if (!clustersData || !clustersData.clusters || clustersData.clusters.length === 0) {
        // Add a default marker showing the area
        L.circleMarker(PLAINFIELD_CENTER, {
            radius: 20,
            fillColor: "#58a6ff",
            color: "#fff",
            weight: 2,
            opacity: 0.8,
            fillOpacity: 0.3,
        })
        .bindPopup("<strong>Plainfield, NJ</strong><br>No active clusters at this time.")
        .addTo(map);
        return;
    }
    
    // Add cluster markers
    clustersData.clusters.forEach(cluster => {
        addClusterMarker(cluster);
    });
}

function addClusterMarker(cluster) {
    // Normalize ZIP code to 5 digits for lookup
    const zip5 = String(cluster.zip).padStart(5, '0');
    const coords = ZIP_COORDS[zip5] || ZIP_COORDS[cluster.zip] || PLAINFIELD_CENTER;
    
    // Add some jitter to prevent exact overlaps
    const jitter = () => (Math.random() - 0.5) * 0.005;
    const markerCoords = [coords[0] + jitter(), coords[1] + jitter()];
    
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
    
    const marker = L.circleMarker(markerCoords, {
        radius: radius,
        fillColor: fillColor,
        color: color,
        weight: 3,
        opacity: 0.9,
        fillOpacity: 0.4,
    });
    
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
                const domain = new URL(url).hostname.replace('www.', '');
                return `<a href="${url}" target="_blank" rel="noopener" style="color: var(--accent); font-size: 0.8em; display: block; margin: 2px 0; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">🔗 ${domain}</a>`;
            }).join('')}
           </div>` 
        : '';
    
    const popupContent = `
        <div style="background: var(--bg); color: var(--text); padding: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <strong style="font-size: 1.1em;">Cluster #${cluster.id}</strong>
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
            </div>
            ${mediaLinksHtml}
        </div>
    `;
    
    marker.bindPopup(popupContent, {
        maxWidth: 280,
    });
    
    marker.addTo(map);
}

// ============================================
// Data Loading
// ============================================

async function loadData() {
    try {
        // Detect if we're on CloudFront or S3 and adjust paths accordingly
        const baseUrl = window.location.hostname.includes('cloudfront') 
            ? 'https://heat-plainfield.s3.us-east-1.amazonaws.com/'
            : './';
        
        const [clustersRes, timelineRes, keywordsRes] = await Promise.all([
            fetch(baseUrl + "data/clusters.json"),
            fetch(baseUrl + "data/timeline.json"),
            fetch(baseUrl + "data/keywords.json"),
        ]);
        
        if (clustersRes.ok) {
            clustersData = await clustersRes.json();
            console.log("Loaded clusters:", clustersData);
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
        
    } catch (error) {
        console.error("Failed to load data:", error);
        clustersData = { clusters: [] };
        timelineData = { weeks: [] };
    }
}

// ============================================
// Cluster Cards
// ============================================

function renderClusters() {
    const container = document.getElementById("cluster-cards");
    
    if (!clustersData || !clustersData.clusters || clustersData.clusters.length === 0) {
        container.innerHTML = `
            <div class="no-data">
                <p>No active attention clusters at this time.</p>
                <p><small>Clusters appear when multiple public sources reference similar topics.</small></p>
            </div>
        `;
        return;
    }
    
    const html = clustersData.clusters.map(cluster => {
        const strengthClass = cluster.strength > 5 ? "high" : 
                             cluster.strength > 2 ? "medium" : "low";
        const strengthLabel = cluster.strength > 5 ? "High" : 
                             cluster.strength > 2 ? "Medium" : "Low";
        
        const dateRange = formatDateRange(cluster.dateRange.start, cluster.dateRange.end);
        const relativeTime = getRelativeTime(cluster.dateRange.end);
        const status = getSignalStatus(cluster.dateRange.end);
        const sources = Array.isArray(cluster.sources) ? cluster.sources.join(", ") : cluster.sources;
        
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
            <div class="cluster-card" data-cluster-id="${cluster.id}">
                <div class="header">
                    <span class="cluster-id">Cluster #${cluster.id}</span>
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
    
    // Get weeks array (handle both old format and new format)
    const weeks = timelineData.weeks || timelineData || [];
    
    if (!weeks || weeks.length === 0) {
        ctx.parentElement.innerHTML = `
            <div class="no-data">
                <p>No timeline data available.</p>
            </div>
        `;
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
            trendSummary.textContent = "is rising";
            trendSummary.style.color = "var(--danger)";
        } else if (trend.direction === "decreasing") {
            trendSummary.textContent = "is declining";
            trendSummary.style.color = "var(--success)";
        } else {
            trendSummary.textContent = "is stable";
            trendSummary.style.color = "var(--accent)";
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

function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ============================================
// Keywords & NLP Display
// ============================================

function renderKeywords() {
    const cloudContainer = document.getElementById("keyword-cloud");
    const categoryContainer = document.getElementById("category-distribution");
    
    if (!keywordsData) {
        cloudContainer.innerHTML = '<p class="no-data">No keyword data available.</p>';
        return;
    }
    
    // Render keyword cloud
    const keywords = keywordsData.top_keywords || [];
    if (keywords.length > 0) {
        const maxCount = Math.max(...keywords.map(k => k[1]));
        
        const keywordHtml = keywords.map(([word, count], index) => {
            const size = count / maxCount;
            let sizeClass = "";
            if (size > 0.7) sizeClass = "large";
            else if (size > 0.4) sizeClass = "medium";
            
            return `<span class="keyword-tag ${sizeClass}" title="${count} occurrences">${word}</span>`;
        }).join("");
        
        cloudContainer.innerHTML = keywordHtml;
    } else {
        cloudContainer.innerHTML = '<p class="no-data">No keywords extracted yet.</p>';
    }
    
    // Render category distribution
    const categories = keywordsData.categories || {};
    if (Object.keys(categories).length > 0) {
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
    
    let text = "HEAT — Event Log\n";
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
