/**
 * HEAT — Civic Resilience Platform Identity
 * Reframes HEAT as a civic resilience tool, not surveillance.
 * All text bilingual EN/ES.
 *
 * Exposes global HeatPlatform object.
 */
(function () {
    'use strict';

    // =========================================================================
    // PLATFORM MESSAGING CONSTANTS
    // =========================================================================

    var PLATFORM_NAME = 'HEAT \u2014 Civic Resilience Platform';
    var PLATFORM_TAGLINE = 'Community intelligence for civic resilience';
    var PLATFORM_DESCRIPTION = 'HEAT maps collective civic attention patterns to help communities understand, prepare, and respond. Not surveillance \u2014 interpretation.';

    var ABOUT_TEXT = {
        en: [
            'HEAT is a delayed, aggregated civic signal map focused on Plainfield, NJ and surrounding New Jersey communities. It visualizes when immigration-related topics become collectively salient in public discourse \u2014 not a real-time tracker or alert system.',
            'Our core principle is interpretation over surveillance. HEAT does not track individuals, report locations in real time, or serve as an enforcement tool. Instead, it aggregates publicly available news, advocacy reports, and anonymized community input into topic clusters displayed as a heatmap of civic attention.',
            'All data passes through mandatory safety buffers: a minimum 24-hour delay (72 hours for public tier), multi-source corroboration requirements, and volume thresholds that filter noise. No single report can appear on the map \u2014 only patterns confirmed across multiple independent sources.',
            'HEAT is built on the belief that communities have a right to understand the information landscape around them. Informed communities are resilient communities. This tool exists to support civic preparedness, legal empowerment, and community solidarity \u2014 never to enable surveillance or targeting.',
            'PII (personally identifiable information) is scrubbed at every pipeline stage. Geographic precision is limited to ZIP-code level. All community submissions are anonymous by design.',
            'HEAT is community-owned. The methodology, data pipeline, and source code are transparent. No data is sold, shared with enforcement agencies, or used for any purpose beyond civic information.'
        ],
        es: [
            'HEAT es un mapa de señales cívicas agregadas y diferidas centrado en Plainfield, NJ y comunidades circundantes de Nueva Jersey. Visualiza cuándo los temas relacionados con inmigración se vuelven colectivamente relevantes en el discurso público — no es un rastreador en tiempo real ni un sistema de alertas.',
            'Nuestro principio fundamental es interpretación sobre vigilancia. HEAT no rastrea individuos, no reporta ubicaciones en tiempo real ni sirve como herramienta de aplicación de la ley. En cambio, agrega noticias públicamente disponibles, informes de defensoría y aportes comunitarios anonimizados en grupos temáticos mostrados como un mapa de calor de atención cívica.',
            'Todos los datos pasan por amortiguadores de seguridad obligatorios: un retraso mínimo de 24 horas (72 horas para el nivel público), requisitos de corroboración de múltiples fuentes y umbrales de volumen que filtran el ruido. Ningún reporte individual puede aparecer en el mapa — solo patrones confirmados a través de múltiples fuentes independientes.',
            'HEAT se construye sobre la creencia de que las comunidades tienen derecho a comprender el panorama informativo que las rodea. Las comunidades informadas son comunidades resilientes. Esta herramienta existe para apoyar la preparación cívica, el empoderamiento legal y la solidaridad comunitaria — nunca para permitir la vigilancia o el señalamiento.',
            'La información de identificación personal (PII) se elimina en cada etapa del proceso. La precisión geográfica se limita al nivel de código postal. Todas las contribuciones comunitarias son anónimas por diseño.',
            'HEAT es propiedad de la comunidad. La metodología, el proceso de datos y el código fuente son transparentes. Ningún dato se vende, se comparte con agencias de aplicación de la ley ni se utiliza para ningún propósito más allá de la información cívica.'
        ]
    };

    var PLATFORM_TAGLINE_ES = 'Inteligencia comunitaria para la resiliencia cívica';
    var PLATFORM_DESCRIPTION_ES = 'HEAT mapea patrones colectivos de atención cívica para ayudar a las comunidades a comprender, prepararse y responder. No es vigilancia — es interpretación.';

    // =========================================================================
    // LOCALIZED UI
    // =========================================================================

    var STRINGS = {
        en: {
            aboutTitle: 'About HEAT',
            whatIs: 'What HEAT Is',
            whatIsText: 'A delayed civic signal aggregation platform that maps collective attention patterns from public sources. HEAT shows where and when immigration-related topics appear in news, advocacy, and community discourse across New Jersey.',
            whatIsNot: 'What HEAT Is NOT',
            whatIsNotItems: [
                'Not a real-time tracker or surveillance system',
                'Not a tool for law enforcement or immigration agencies',
                'Not a report tracker or location tracker',
                'Not a source of personally identifiable information'
            ],
            dataCollection: 'How Data Is Collected',
            dataCollectionText: 'HEAT aggregates information exclusively from public sources: RSS news feeds, GDELT global event data, public advocacy reports, and anonymous community input submitted through our secure form. No private data, social media scraping, or location tracking is used.',
            privacyTitle: 'Privacy Commitments',
            privacyItems: [
                'All data is delayed 24–72 hours before display',
                'Geographic precision limited to ZIP-code level only',
                'PII (names, addresses, descriptions) scrubbed at every pipeline stage',
                'Multi-source corroboration required — no single-source data displayed',
                'No cookies, analytics, or tracking — all event data is local only',
                'Community submissions are fully anonymous by design'
            ],
            communityTitle: 'Community Ownership',
            communityItems: [
                'Open methodology — our algorithms are documented and transparent',
                'No data is sold or shared with any enforcement agency',
                'Tiered access ensures raw data is handled responsibly',
                'Community moderators govern content and priorities',
                'Built for the community, by the community'
            ],
            methodologyTitle: 'How It Works',
            signalCollection: 'Signal Collection',
            signalCollectionText: 'HEAT continuously monitors public RSS feeds from NJ news outlets, GDELT global event data, public records from city council meetings, and anonymous community submissions. Every source is documented and auditable.',
            safetyBuffer: 'Safety Buffer',
            safetyBufferText: 'All signals pass through mandatory safety checks before display: minimum 24-hour delay (72 hours for public access), requirement of 3+ signals per cluster from 2+ distinct sources, and a volume score threshold that filters noise and prevents single-report amplification.',
            topicIntelligence: 'Topic Intelligence',
            topicIntelligenceText: 'Signals are processed through BERTopic clustering using sentence-transformer embeddings (all-MiniLM-L6-v2) and HDBSCAN density-based clustering. This groups related reports into coherent topic clusters without predetermined categories, letting genuine patterns emerge from the data.',
            sentimentMapping: 'Consensus Mapping',
            sentimentMappingText: 'Inspired by Polis-style opinion mapping, HEAT analyzes sentiment and framing across clusters to identify areas of community consensus and divergence. This reveals not just what is being discussed, but how communities are interpreting events.',
            resourcesTitle: 'Community Resources',
            legalAid: 'Legal Aid Organizations',
            kyrTraining: 'Know Your Rights',
            communityOrgs: 'Community Organizations',
            contributeTitle: 'How to Contribute Safely',
            contributeText: 'You can submit civic signals through our anonymous submission form. No account required. No personally identifying information is collected. Your IP address is not logged. Submissions are processed through the same safety buffer as all other signals.',
            learnMore: 'Learn More',
            close: 'Close'
        },
        es: {
            aboutTitle: 'Acerca de HEAT',
            whatIs: 'Qué es HEAT',
            whatIsText: 'Una plataforma de agregación de señales cívicas diferidas que mapea patrones de atención colectiva de fuentes públicas. HEAT muestra dónde y cuándo aparecen temas relacionados con inmigración en noticias, defensoría y discurso comunitario en Nueva Jersey.',
            whatIsNot: 'Qué NO es HEAT',
            whatIsNotItems: [
                'No es un rastreador en tiempo real ni un sistema de vigilancia',
                'No es una herramienta para la policía o agencias de inmigración',
                'No es un rastreador de reportes o de ubicación',
                'No es una fuente de información personal identificable'
            ],
            dataCollection: 'Cómo Se Recopilan los Datos',
            dataCollectionText: 'HEAT agrega información exclusivamente de fuentes públicas: feeds RSS de noticias, datos globales GDELT, informes públicos de defensoría y aportes comunitarios anónimos enviados a través de nuestro formulario seguro. No se usa datos privados, raspado de redes sociales ni rastreo de ubicación.',
            privacyTitle: 'Compromisos de Privacidad',
            privacyItems: [
                'Todos los datos se retrasan 24–72 horas antes de mostrarse',
                'Precisión geográfica limitada solo al nivel de código postal',
                'PII (nombres, direcciones, descripciones) eliminados en cada etapa',
                'Se requiere corroboración de múltiples fuentes — no se muestra datos de una sola fuente',
                'Sin cookies, analíticas o rastreo — todos los datos de eventos son locales',
                'Las contribuciones comunitarias son completamente anónimas por diseño'
            ],
            communityTitle: 'Propiedad Comunitaria',
            communityItems: [
                'Metodología abierta — nuestros algoritmos están documentados y son transparentes',
                'Ningún dato se vende o comparte con agencias de aplicación de la ley',
                'El acceso por niveles asegura que los datos crudos se manejen responsablemente',
                'Moderadores comunitarios gobiernan el contenido y las prioridades',
                'Construido para la comunidad, por la comunidad'
            ],
            methodologyTitle: 'Cómo Funciona',
            signalCollection: 'Recopilación de Señales',
            signalCollectionText: 'HEAT monitorea continuamente feeds RSS públicos de medios de NJ, datos globales GDELT, registros públicos de reuniones del consejo municipal y envíos comunitarios anónimos. Cada fuente está documentada y es auditable.',
            safetyBuffer: 'Amortiguador de Seguridad',
            safetyBufferText: 'Todas las señales pasan por verificaciones de seguridad obligatorias antes de mostrarse: retraso mínimo de 24 horas (72 horas para acceso público), requisito de 3+ señales por grupo de 2+ fuentes distintas, y un umbral de volumen que filtra ruido y previene la amplificación de reportes individuales.',
            topicIntelligence: 'Inteligencia de Temas',
            topicIntelligenceText: 'Las señales se procesan a través de agrupamiento BERTopic usando embeddings de sentence-transformer (all-MiniLM-L6-v2) y agrupamiento basado en densidad HDBSCAN. Esto agrupa reportes relacionados en grupos temáticos coherentes sin categorías predeterminadas, permitiendo que patrones genuinos emerjan de los datos.',
            sentimentMapping: 'Mapeo de Consenso',
            sentimentMappingText: 'Inspirado en el mapeo de opinión estilo Polis, HEAT analiza el sentimiento y el encuadre a través de los grupos para identificar áreas de consenso y divergencia comunitaria. Esto revela no solo qué se está discutiendo, sino cómo las comunidades están interpretando los eventos.',
            resourcesTitle: 'Recursos Comunitarios',
            legalAid: 'Organizaciones de Asistencia Legal',
            kyrTraining: 'Conozca Sus Derechos',
            communityOrgs: 'Organizaciones Comunitarias',
            contributeTitle: 'Cómo Contribuir de Forma Segura',
            contributeText: 'Puede enviar señales cívicas a través de nuestro formulario anónimo. No se requiere cuenta. No se recopila información personal identificable. Su dirección IP no se registra. Los envíos se procesan a través del mismo amortiguador de seguridad que todas las demás señales.',
            learnMore: 'Saber Más',
            close: 'Cerrar'
        }
    };

    // =========================================================================
    // COMMUNITY RESOURCES DATA
    // =========================================================================

    var LEGAL_AID_ORGS = [
        {
            name: { en: 'Legal Services of New Jersey', es: 'Servicios Legales de Nueva Jersey' },
            desc: { en: 'Free legal help for low-income NJ residents.', es: 'Ayuda legal gratuita para residentes de NJ de bajos ingresos.' },
            phone: '1-888-576-5529',
            url: 'https://www.lsnj.org'
        },
        {
            name: { en: 'ACLU of New Jersey', es: 'ACLU de Nueva Jersey' },
            desc: { en: 'Civil liberties defense and Know Your Rights resources.', es: 'Defensa de libertades civiles y recursos de Conozca Sus Derechos.' },
            phone: '(973) 642-2084',
            url: 'https://www.aclu-nj.org'
        },
        {
            name: { en: 'American Immigration Lawyers Association (NJ Chapter)', es: 'Asociación Americana de Abogados de Inmigración (Capítulo NJ)' },
            desc: { en: 'Find an immigration attorney in New Jersey.', es: 'Encuentre un abogado de inmigración en Nueva Jersey.' },
            phone: '',
            url: 'https://www.aila.org'
        },
        {
            name: { en: 'Catholic Charities, Diocese of Metuchen', es: 'Caridades Católicas, Diócesis de Metuchen' },
            desc: { en: 'Immigration legal services and social support.', es: 'Servicios legales de inmigración y apoyo social.' },
            phone: '(732) 324-8200',
            url: 'https://www.ccdom.org'
        }
    ];

    var COMMUNITY_ORGS = [
        {
            name: { en: 'NJ Alliance for Immigrant Justice', es: 'Alianza NJ por la Justicia Inmigrante' },
            desc: { en: 'Statewide coalition for immigrant rights.', es: 'Coalición estatal por los derechos de los inmigrantes.' },
            url: 'https://www.immigrantjusticenj.org'
        },
        {
            name: { en: 'Wind of the Spirit Immigrant Resource Center', es: 'Centro de Recursos para Inmigrantes Wind of the Spirit' },
            desc: { en: 'Community organizing, legal clinics, and advocacy in central NJ.', es: 'Organización comunitaria, clínicas legales y defensoría en el centro de NJ.' },
            phone: '(862) 262-8337',
            url: 'https://windofthespirit.net'
        },
        {
            name: { en: 'American Friends Service Committee — NJ', es: 'American Friends Service Committee — NJ' },
            desc: { en: 'Immigrant rights programs, accompaniment, and legal support.', es: 'Programas de derechos inmigrantes, acompañamiento y apoyo legal.' },
            phone: '(973) 643-1924',
            url: 'https://www.afsc.org/office/newark-nj'
        },
        {
            name: { en: 'Make the Road New Jersey', es: 'Make the Road Nueva Jersey' },
            desc: { en: 'Community power building and immigrant justice.', es: 'Construcción de poder comunitario y justicia inmigrante.' },
            url: 'https://maketheroadnj.org'
        }
    ];

    var KYR_EVENTS = [
        {
            name: { en: 'Know Your Rights Training (ACLU NJ)', es: 'Capacitación "Conozca Sus Derechos" (ACLU NJ)' },
            desc: { en: 'Regular community trainings on rights during ICE encounters. Check ACLU-NJ.org for schedule.', es: 'Capacitaciones comunitarias regulares sobre derechos durante encuentros con ICE. Consulte ACLU-NJ.org para el calendario.' },
            url: 'https://www.aclu-nj.org/know-your-rights'
        },
        {
            name: { en: 'Legal Clinics (Catholic Charities)', es: 'Clínicas Legales (Caridades Católicas)' },
            desc: { en: 'Free immigration legal consultations in Middlesex and Union counties.', es: 'Consultas legales gratuitas de inmigración en los condados de Middlesex y Union.' },
            url: 'https://www.ccdom.org'
        }
    ];

    // =========================================================================
    // STATE
    // =========================================================================

    var currentLang = 'en';
    var aboutPanelEl = null;
    var methodologyPanelEl = null;
    var resourcesPanelEl = null;

    // =========================================================================
    // HELPERS
    // =========================================================================

    function t(key) {
        return (STRINGS[currentLang] || STRINGS.en)[key] || key;
    }

    function esc(str) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(str || ''));
        return d.innerHTML;
    }

    function detectLang() {
        try {
            var sel = document.getElementById('lang-select');
            if (sel && sel.value === 'es') { currentLang = 'es'; return; }
            var stored = localStorage.getItem('heat_emergency_lang');
            if (stored === 'es') { currentLang = 'es'; return; }
        } catch (e) { /* */ }
        currentLang = 'en';
    }

    // =========================================================================
    // RENDER — ABOUT PANEL
    // =========================================================================

    function renderAboutPanel(container) {
        var wrap = container || document.createElement('div');
        wrap.className = 'platform-panel platform-about';
        wrap.setAttribute('role', 'region');
        wrap.setAttribute('aria-label', t('aboutTitle'));

        var html = '';
        html += '<h2 class="platform-panel__title">' + esc(t('aboutTitle')) + '</h2>';

        // What HEAT is
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">' + esc(t('whatIs')) + '</h3>';
        html += '<p>' + esc(t('whatIsText')) + '</p>';
        html += '</section>';

        // What HEAT is NOT
        html += '<section class="platform-section platform-section--not">';
        html += '<h3 class="platform-section__heading">' + esc(t('whatIsNot')) + '</h3>';
        html += '<ul class="platform-list platform-list--not">';
        t('whatIsNotItems').forEach(function (item) {
            html += '<li>❌ ' + esc(item) + '</li>';
        });
        html += '</ul>';
        html += '</section>';

        // How data is collected
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">' + esc(t('dataCollection')) + '</h3>';
        html += '<p>' + esc(t('dataCollectionText')) + '</p>';
        html += '</section>';

        // Privacy
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">🔒 ' + esc(t('privacyTitle')) + '</h3>';
        html += '<ul class="platform-list">';
        t('privacyItems').forEach(function (item) {
            html += '<li>✓ ' + esc(item) + '</li>';
        });
        html += '</ul>';
        html += '</section>';

        // Community ownership
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">' + esc(t('communityTitle')) + '</h3>';
        html += '<ul class="platform-list">';
        t('communityItems').forEach(function (item) {
            html += '<li>• ' + esc(item) + '</li>';
        });
        html += '</ul>';
        html += '</section>';

        // Full about text
        html += '<section class="platform-section platform-section--about-full">';
        var paragraphs = ABOUT_TEXT[currentLang] || ABOUT_TEXT.en;
        paragraphs.forEach(function (p) {
            html += '<p>' + esc(p) + '</p>';
        });
        html += '</section>';

        wrap.innerHTML = html;
        aboutPanelEl = wrap;
        return wrap;
    }

    // =========================================================================
    // RENDER — METHODOLOGY PANEL
    // =========================================================================

    function renderMethodologyPanel(container) {
        var wrap = container || document.createElement('div');
        wrap.className = 'platform-panel platform-methodology';
        wrap.setAttribute('role', 'region');
        wrap.setAttribute('aria-label', t('methodologyTitle'));

        var sections = [
            { heading: t('signalCollection'), text: t('signalCollectionText'), icon: '📡' },
            { heading: t('safetyBuffer'), text: t('safetyBufferText'), icon: '🛡️' },
            { heading: t('topicIntelligence'), text: t('topicIntelligenceText'), icon: '🧠' },
            { heading: t('sentimentMapping'), text: t('sentimentMappingText'), icon: '🗺️' }
        ];

        var html = '';
        html += '<h2 class="platform-panel__title">' + esc(t('methodologyTitle')) + '</h2>';

        sections.forEach(function (sec, i) {
            html += '<section class="platform-method-card">';
            html += '<div class="platform-method-card__step">' + (i + 1) + '</div>';
            html += '<div class="platform-method-card__content">';
            html += '<h3>' + sec.icon + ' ' + esc(sec.heading) + '</h3>';
            html += '<p>' + esc(sec.text) + '</p>';
            html += '</div>';
            html += '</section>';
        });

        wrap.innerHTML = html;
        methodologyPanelEl = wrap;
        return wrap;
    }

    // =========================================================================
    // RENDER — COMMUNITY RESOURCES
    // =========================================================================

    function renderCommunityResources(container) {
        var wrap = container || document.createElement('div');
        wrap.className = 'platform-panel platform-resources';
        wrap.setAttribute('role', 'region');
        wrap.setAttribute('aria-label', t('resourcesTitle'));

        var html = '';
        html += '<h2 class="platform-panel__title">' + esc(t('resourcesTitle')) + '</h2>';

        // Legal Aid
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">⚖️ ' + esc(t('legalAid')) + '</h3>';
        html += '<div class="platform-resource-cards">';
        LEGAL_AID_ORGS.forEach(function (org) {
            html += renderResourceCard(org);
        });
        html += '</div>';
        html += '</section>';

        // KYR Events
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">📋 ' + esc(t('kyrTraining')) + '</h3>';
        html += '<div class="platform-resource-cards">';
        KYR_EVENTS.forEach(function (evt) {
            html += renderResourceCard(evt);
        });
        html += '</div>';
        html += '</section>';

        // Community Orgs
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">🤝 ' + esc(t('communityOrgs')) + '</h3>';
        html += '<div class="platform-resource-cards">';
        COMMUNITY_ORGS.forEach(function (org) {
            html += renderResourceCard(org);
        });
        html += '</div>';
        html += '</section>';

        // How to Contribute
        html += '<section class="platform-section">';
        html += '<h3 class="platform-section__heading">📤 ' + esc(t('contributeTitle')) + '</h3>';
        html += '<p>' + esc(t('contributeText')) + '</p>';
        html += '<a href="submit.html" class="platform-contribute-link">→ ' + esc(t('contributeTitle')) + '</a>';
        html += '</section>';

        wrap.innerHTML = html;
        resourcesPanelEl = wrap;
        return wrap;
    }

    function renderResourceCard(resource) {
        var name = resource.name[currentLang] || resource.name.en;
        var desc = resource.desc[currentLang] || resource.desc.en;
        var html = '<div class="platform-resource-card">';
        html += '<div class="platform-resource-card__name">' + esc(name) + '</div>';
        html += '<div class="platform-resource-card__desc">' + esc(desc) + '</div>';
        if (resource.phone) {
            html += '<a href="tel:' + esc(resource.phone.replace(/[^\d+]/g, '')) + '" class="platform-resource-card__phone">📞 ' + esc(resource.phone) + '</a>';
        }
        if (resource.url) {
            html += '<a href="' + esc(resource.url) + '" target="_blank" rel="noopener" class="platform-resource-card__link">🔗 ' + esc(resource.url.replace(/^https?:\/\//, '')) + '</a>';
        }
        html += '</div>';
        return html;
    }

    // =========================================================================
    // FULL COMBINED PANEL (modal-style)
    // =========================================================================

    var combinedPanelEl = null;

    function showPlatformPanel(section) {
        closePlatformPanel();

        combinedPanelEl = document.createElement('div');
        combinedPanelEl.className = 'platform-overlay';
        combinedPanelEl.setAttribute('role', 'dialog');
        combinedPanelEl.setAttribute('aria-modal', 'true');
        combinedPanelEl.setAttribute('aria-label', PLATFORM_NAME);

        var html = '';
        html += '<div class="platform-overlay__inner">';

        // Header
        html += '<div class="platform-overlay__header">';
        html += '<h1 class="platform-overlay__brand">' + esc(PLATFORM_NAME) + '</h1>';
        html += '<p class="platform-overlay__tagline">' + esc(currentLang === 'es' ? PLATFORM_TAGLINE_ES : PLATFORM_TAGLINE) + '</p>';
        html += '<button class="platform-overlay__close" id="platform-close" aria-label="' + esc(t('close')) + '">✕</button>';
        html += '</div>';

        // Tab nav
        html += '<nav class="platform-tabs" role="tablist">';
        html += '<button class="platform-tab' + (section === 'about' ? ' active' : '') + '" data-tab="about" role="tab">📖 ' + esc(t('aboutTitle')) + '</button>';
        html += '<button class="platform-tab' + (section === 'methodology' ? ' active' : '') + '" data-tab="methodology" role="tab">🔬 ' + esc(t('methodologyTitle')) + '</button>';
        html += '<button class="platform-tab' + (section === 'resources' ? ' active' : '') + '" data-tab="resources" role="tab">🤝 ' + esc(t('resourcesTitle')) + '</button>';
        html += '</nav>';

        // Tab content containers
        html += '<div class="platform-tab-content" id="platform-tab-content"></div>';

        html += '</div>';
        combinedPanelEl.innerHTML = html;

        document.body.appendChild(combinedPanelEl);
        document.body.style.overflow = 'hidden';

        // Render initial tab
        renderTab(section || 'about');

        // Bind events
        combinedPanelEl.querySelector('#platform-close').addEventListener('click', closePlatformPanel);
        combinedPanelEl.querySelectorAll('.platform-tab').forEach(function (tab) {
            tab.addEventListener('click', function () {
                combinedPanelEl.querySelectorAll('.platform-tab').forEach(function (t) { t.classList.remove('active'); });
                tab.classList.add('active');
                renderTab(tab.getAttribute('data-tab'));
            });
        });
        combinedPanelEl.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closePlatformPanel();
        });

        // Click outside to close
        combinedPanelEl.addEventListener('click', function (e) {
            if (e.target === combinedPanelEl) closePlatformPanel();
        });
    }

    function renderTab(tab) {
        var container = combinedPanelEl.querySelector('#platform-tab-content');
        if (!container) return;
        container.innerHTML = '';
        switch (tab) {
            case 'about': renderAboutPanel(container); break;
            case 'methodology': renderMethodologyPanel(container); break;
            case 'resources': renderCommunityResources(container); break;
        }
    }

    function closePlatformPanel() {
        if (combinedPanelEl && combinedPanelEl.parentNode) {
            combinedPanelEl.parentNode.removeChild(combinedPanelEl);
        }
        combinedPanelEl = null;
        document.body.style.overflow = '';
    }

    // =========================================================================
    // PLATFORM BRANDING INIT
    // =========================================================================

    function initPlatformIdentity() {
        detectLang();

        // Update page title with platform name
        if (document.title) {
            document.title = PLATFORM_NAME + ' | ' + (currentLang === 'es' ? PLATFORM_TAGLINE_ES : PLATFORM_TAGLINE);
        }

        // Update meta description if present
        var metaDesc = document.querySelector('meta[name="description"]');
        if (!metaDesc) {
            metaDesc = document.createElement('meta');
            metaDesc.setAttribute('name', 'description');
            document.head.appendChild(metaDesc);
        }
        metaDesc.setAttribute('content', currentLang === 'es' ? PLATFORM_DESCRIPTION_ES : PLATFORM_DESCRIPTION);

        // Listen for lang changes
        var sel = document.getElementById('lang-select');
        if (sel) {
            sel.addEventListener('change', function () {
                currentLang = sel.value === 'es' ? 'es' : 'en';
            });
        }
    }

    // =========================================================================
    // PUBLIC API — global HeatPlatform
    // =========================================================================

    var HeatPlatform = {
        // Constants
        PLATFORM_NAME: PLATFORM_NAME,
        PLATFORM_TAGLINE: PLATFORM_TAGLINE,
        PLATFORM_DESCRIPTION: PLATFORM_DESCRIPTION,
        ABOUT_TEXT: ABOUT_TEXT,

        // Init
        initPlatformIdentity: initPlatformIdentity,

        // Renderers
        renderAboutPanel: renderAboutPanel,
        renderMethodologyPanel: renderMethodologyPanel,
        renderCommunityResources: renderCommunityResources,

        // Combined panel
        show: showPlatformPanel,
        showAbout: function () { showPlatformPanel('about'); },
        showMethodology: function () { showPlatformPanel('methodology'); },
        showResources: function () { showPlatformPanel('resources'); },
        close: closePlatformPanel,

        // Data
        getLegalAidOrgs: function () { return LEGAL_AID_ORGS; },
        getCommunityOrgs: function () { return COMMUNITY_ORGS; },
        getKYREvents: function () { return KYR_EVENTS; },

        // Language
        setLang: function (lang) {
            currentLang = (lang === 'es') ? 'es' : 'en';
        },
        getLang: function () { return currentLang; }
    };

    window.HeatPlatform = HeatPlatform;

    // Auto-init when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPlatformIdentity);
    } else {
        initPlatformIdentity();
    }

})();
