/**
 * HEAT Data Export Dashboard JavaScript
 * Interactive data exploration with filtering, charts, and search
 */

let visualizationData = null;
let clustersData = null;
let allClusters = [];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    setupTabs();
    await loadData();
    renderSummary();
    renderCharts();
    renderTables();
    setupFilters();
});

// Tab Navigation
function setupTabs() {
    const tabs = document.querySelectorAll('.export-tab');
    const contents = document.querySelectorAll('.export-tab-content');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            
            // Update active tab
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Show corresponding content
            contents.forEach(content => {
                if (content.dataset.tabContent === targetTab) {
                    content.classList.add('active');
                } else {
                    content.classList.remove('active');
                }
            });
        });
    });
}

// Load Data
async function loadData() {
    try {
        const baseUrl = getBaseUrl();
        
        // Load visualization metadata
        const vizRes = await fetch(baseUrl + 'data/visualization_metadata.json');
        if (vizRes.ok) {
            visualizationData = await vizRes.json();
        }
        
        // Load reported locations (detailed cluster data)
        const clusterRes = await fetch(baseUrl + 'data/reported_locations.json');
        if (clusterRes.ok) {
            clustersData = await clusterRes.json();
            allClusters = clustersData.records || [];
        }
        
        // Update last updated time
        if (visualizationData?.generated_at) {
            document.getElementById('last-updated').textContent = 
                new Date(visualizationData.generated_at).toLocaleString();
        }
        
    } catch (error) {
        console.error('Failed to load data:', error);
    }
}

function getBaseUrl() {
    return window.location.hostname.includes('cloudfront')
        ? 'https://heat-plainfield.s3.us-east-1.amazonaws.com/'
        : './';
}

// Render Summary
function renderSummary() {
    if (!visualizationData?.summary) return;
    
    const summary = visualizationData.summary;
    
    document.getElementById('total-clusters').textContent = summary.total_clusters || 0;
    document.getElementById('total-records').textContent = summary.total_records || 0;
    document.getElementById('unique-zips').textContent = summary.unique_zips || 0;
    document.getElementById('unique-sources').textContent = summary.unique_sources || 0;
    
    if (summary.date_range) {
        const start = new Date(summary.date_range.start);
        const end = new Date(summary.date_range.end);
        const duration = Math.floor((end - start) / (1000 * 60 * 60 * 24));
        
        document.getElementById('date-start').textContent = start.toLocaleDateString();
        document.getElementById('date-end').textContent = end.toLocaleDateString();
        document.getElementById('date-duration').textContent = duration;
    }
}

// Render Charts
function renderCharts() {
    if (!visualizationData?.charts) return;
    
    visualizationData.charts.forEach(chart => {
        const canvas = document.getElementById(`chart-${chart.id.replace('_', '-')}`);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        let chartConfig = {
            type: chart.type === 'histogram' ? 'bar' : chart.type,
            data: {
                labels: chart.data.labels || [],
                datasets: [{
                    label: chart.title,
                    data: chart.data.values || [],
                    backgroundColor: chart.options?.color || '#ff6b35',
                    borderColor: chart.options?.color || '#ff6b35',
                    borderWidth: 2,
                    fill: chart.options?.fill || false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: chart.type === 'pie'
                    },
                    title: {
                        display: false
                    }
                },
                scales: chart.type !== 'pie' ? {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: chart.options?.ylabel || ''
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: chart.options?.xlabel || ''
                        }
                    }
                } : undefined
            }
        };
        
        // Special handling for pie charts
        if (chart.type === 'pie') {
            chartConfig.data.datasets[0].backgroundColor = chart.options?.colors || [
                '#ff6b35', '#26a641', '#ffa500', '#ee675c', '#81c995', '#fdd663', '#f28b82', '#8b949e'
            ];
        }
        
        new Chart(ctx, chartConfig);
    });
}

// Render Tables
function renderTables() {
    renderClustersTable();
    renderTimelineTable();
    renderSourcesTable();
}

function renderClustersTable(filteredData = null) {
    const container = document.getElementById('clusters-table');
    if (!container) return;
    
    const data = filteredData || allClusters;
    
    if (!data || data.length === 0) {
        container.innerHTML = '<p style="padding: 2rem; text-align: center;">No cluster data available</p>';
        return;
    }
    
    let html = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>ZIP</th>
                    <th>Location</th>
                    <th>Size</th>
                    <th>Strength</th>
                    <th>Quality</th>
                    <th>Sources</th>
                    <th>Period</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    data.forEach(cluster => {
        const trackingId = `HEAT-CLU-${String(cluster.cluster_id).padStart(6, '0')}`;
        const qualityClass = (cluster.quality_score >= 70) ? 'high' : 
                            (cluster.quality_score >= 50) ? 'medium' : 'low';
        const qualityLabel = (cluster.quality_score >= 70) ? 'HIGH' : 
                            (cluster.quality_score >= 50) ? 'MEDIUM' : 'LOW';
        
        html += `
            <tr onclick="viewClusterDetails('${trackingId}')" style="cursor: pointer;">
                <td><span class="tracking-id">${trackingId}</span></td>
                <td>${cluster.zip || '--'}</td>
                <td>${cluster.location_name || '--'}</td>
                <td>${cluster.size || 0}</td>
                <td>${(cluster.strength || 0).toFixed(1)}</td>
                <td><span class="quality-badge quality-${qualityClass}">${qualityLabel}</span></td>
                <td>${cluster.source_count || 0}</td>
                <td>${formatDateShort(cluster.start_date)} - ${formatDateShort(cluster.end_date)}</td>
            </tr>
        `;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

function renderTimelineTable() {
    const container = document.getElementById('timeline-table');
    if (!container) return;
    
    // We'll need to fetch this from comprehensive CSV or generate from records
    container.innerHTML = '<p style="padding: 2rem;">Timeline data available in comprehensive CSV export</p>';
}

function renderSourcesTable() {
    const container = document.getElementById('sources-table');
    if (!container) return;
    
    container.innerHTML = '<p style="padding: 2rem;">Source tracking data available in comprehensive CSV export</p>';
}

// Filters
function setupFilters() {
    // Populate ZIP filter
    const zipFilter = document.getElementById('filter-zip');
    if (zipFilter && allClusters.length > 0) {
        const uniqueZips = [...new Set(allClusters.map(c => c.zip))].sort();
        uniqueZips.forEach(zip => {
            const option = document.createElement('option');
            option.value = zip;
            option.textContent = zip;
            zipFilter.appendChild(option);
        });
    }
    
    // Attach filter listeners
    ['filter-zip', 'filter-quality', 'filter-size'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', applyFilters);
        }
    });
}

function applyFilters() {
    const zipFilter = document.getElementById('filter-zip')?.value;
    const qualityFilter = document.getElementById('filter-quality')?.value;
    const sizeFilter = parseInt(document.getElementById('filter-size')?.value) || 0;
    
    let filtered = allClusters;
    
    if (zipFilter) {
        filtered = filtered.filter(c => c.zip === zipFilter);
    }
    
    if (qualityFilter) {
        filtered = filtered.filter(c => {
            const quality = c.quality_score >= 70 ? 'HIGH' :
                          c.quality_score >= 50 ? 'MEDIUM' : 'LOW';
            return quality === qualityFilter;
        });
    }
    
    if (sizeFilter > 0) {
        filtered = filtered.filter(c => (c.size || 0) >= sizeFilter);
    }
    
    renderClustersTable(filtered);
}

// Tracking Search
function searchTracking() {
    const searchTerm = document.getElementById('tracking-search')?.value.trim();
    if (!searchTerm) return;
    
    // Extract cluster ID from tracking ID
    const match = searchTerm.match(/HEAT-CLU-(\d+)/i);
    const clusterId = match ? parseInt(match[1]) : parseInt(searchTerm);
    
    const cluster = allClusters.find(c => c.cluster_id === clusterId);
    const resultsContainer = document.getElementById('tracking-results');
    
    if (!cluster) {
        resultsContainer.innerHTML = `
            <div class="glass-card" style="padding: var(--space-lg); text-align: center;">
                <p style="color: var(--danger);">❌ Cluster not found</p>
                <p class="muted-text">Check the tracking ID and try again</p>
            </div>
        `;
        return;
    }
    
    resultsContainer.innerHTML = `
        <div class="tracking-item glass-card">
            <h3>Cluster Details</h3>
            <p><strong>Tracking ID:</strong> <span class="tracking-id">HEAT-CLU-${String(cluster.cluster_id).padStart(6, '0')}</span></p>
            <p><strong>ZIP Code:</strong> ${cluster.zip} (${cluster.location_name})</p>
            <p><strong>Coordinates:</strong> ${cluster.latitude}, ${cluster.longitude}</p>
            <p><strong>Size:</strong> ${cluster.size} signals</p>
            <p><strong>Strength:</strong> ${(cluster.strength || 0).toFixed(2)}</p>
            <p><strong>Quality Score:</strong> ${(cluster.quality_score || 0).toFixed(1)}/100</p>
            <p><strong>Confidence:</strong> ${cluster.confidence_level || 'N/A'}</p>
            <p><strong>Period:</strong> ${formatDate(cluster.start_date)} to ${formatDate(cluster.end_date)}</p>
            <p><strong>Duration:</strong> ${cluster.duration_days || 0} days</p>
            <p><strong>Sources:</strong> ${cluster.source_list || 'N/A'}</p>
            <p><strong>Source Count:</strong> ${cluster.source_count || 0}</p>
            
            <h4 style="margin-top: var(--space-md);">Summary</h4>
            <p style="font-style: italic;">"${cluster.summary || 'No summary available'}"</p>
            
            ${cluster.media_links ? `
                <h4 style="margin-top: var(--space-md);">Media Links</h4>
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    ${cluster.media_links.split(' | ').map(link => 
                        `<a href="${link}" target="_blank" rel="noopener" style="color: var(--accent);">${link}</a>`
                    ).join('')}
                </div>
            ` : ''}
        </div>
    `;
}

window.searchTracking = searchTracking;

function viewClusterDetails(trackingId) {
    // Switch to tracking tab
    const trackingTab = document.querySelector('[data-tab="tracking"]');
    if (trackingTab) {
        trackingTab.click();
    }
    
    // Set search value and trigger search
    const searchInput = document.getElementById('tracking-search');
    if (searchInput) {
        searchInput.value = trackingId;
        searchTracking();
    }
}

window.viewClusterDetails = viewClusterDetails;

// Utility Functions
function formatDate(dateStr) {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleDateString();
}

function formatDateShort(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return `${date.getMonth() + 1}/${date.getDate()}`;
}
