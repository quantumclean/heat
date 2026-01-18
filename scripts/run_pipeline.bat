@echo off
REM HEAT - Run Data Processing Pipeline
REM Full pipeline: RSS scraping -> ingestion -> clustering -> NLP -> alerts -> buffer -> export -> tiers

echo ========================================
echo HEAT Data Processing Pipeline
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/9] Fetching RSS feeds...
python processing\rss_scraper.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: RSS scraping failed, continuing with existing data...
)

echo.
echo [2/9] Running ingestion...
python processing\ingest.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Ingestion failed!
    pause
    exit /b 1
)

echo.
echo [3/9] Running clustering (HDBSCAN + embeddings)...
python processing\cluster.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Clustering failed!
    pause
    exit /b 1
)

echo.
echo [4/9] Running NLP analysis (keywords, bursts, trends)...
python processing\nlp_analysis.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: NLP analysis failed, continuing...
)

echo.
echo [5/9] Generating heatmap data (KDE)...
python processing\heatmap.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Heatmap generation failed, continuing...
)

echo.
echo [6/9] Applying safety buffer (24hr delay)...
python processing\buffer.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Buffer failed!
    pause
    exit /b 1
)

echo.
echo [7/9] Exporting static files...
python processing\export_static.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Export failed!
    pause
    exit /b 1
)

echo.
echo [8/9] Generating alerts (weekly digest)...
python processing\alerts.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Alert generation failed, continuing...
)

echo.
echo [9/11] Generating tiered access exports...
python processing\tiers.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Tiered exports failed, continuing...
)

echo.
echo [10/11] Running advanced analytics (predictive + performance)...
python processing\advanced_analytics.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Advanced analytics failed, continuing...
)

echo.
echo [11/13] Generating dashboard visualizations...
python processing\dashboard_generator.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Dashboard generation failed, continuing...
)

echo.
echo [12/13] Generating portable intelligence artifacts...
python processing\intelligence_exports.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Intelligence export failed, continuing...
)

echo.
echo [13/13] Legacy tiered exports (backward compatibility)...
python processing\tiers.py
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Legacy tiered export failed, continuing...
)

echo.
echo ========================================
echo Pipeline complete!
echo ========================================
echo.
echo Static files: build\data\
echo Intelligence artifacts: build\exports\
echo   - intelligence_civic_attention.json (self-describing, graph-ready)
echo   - intelligence_system_performance.json (metrics + interpretability)
echo   - intelligence_geographic.json (geospatial + decision framing)
echo Legacy tier exports: build\exports\
echo   - tier0_public.json    (delayed, aggregated)
echo   - tier1_contributor.json (pattern alerts)
echo   - tier2_moderator.json (admin review)
echo   - weekly_digest.json   (subscriber digest)
echo.
echo To preview: cd build ^&^& python -m http.server 8000
echo ========================================
pause
