/**
 * HEAT — Emergency Mode
 * Local-first emergency features for community safety.
 * Progressive enhancement — does not break if JS fails.
 *
 * Exposes global HeatEmergency object.
 */
(function () {
    'use strict';

    // =========================================================================
    // CONSTANTS
    // =========================================================================

    const DB_NAME = 'heat-emergency';
    const DB_VERSION = 1;
    const STORES = {
        heatmap: 'heatmap-cache',
        clusters: 'cluster-cache',
        kyr: 'kyr-cache',
        meta: 'meta'
    };

    const CONTACTS_KEY = 'heat_emergency_contacts';
    const LANG_KEY = 'heat_emergency_lang';

    // Pre-written bilingual SMS templates
    const SMS_TEMPLATES = {
        legalAid: {
            en: 'I need legal assistance immediately. Please help.',
            es: 'Necesito asistencia legal inmediatamente. Por favor ayúdeme.'
        },
        contactOrg: {
            en: 'Please contact a legal aid organization for me. I need help urgently.',
            es: 'Por favor contacte una organización de asistencia legal por mí. Necesito ayuda urgentemente.'
        },
        customPlaceholder: {
            en: 'Type your message here…',
            es: 'Escriba su mensaje aquí…'
        }
    };

    // Know Your Rights content — EN / ES bilingual
    const KYR_CONTENT = [
        {
            id: 'silent',
            icon: '🤐',
            title: { en: 'Right to Remain Silent', es: 'Derecho a Guardar Silencio' },
            body: {
                en: 'You have the right to remain silent. You do not have to answer questions about where you were born, your immigration status, or how you entered the U.S. Say: "I am exercising my right to remain silent."',
                es: 'Usted tiene derecho a guardar silencio. No tiene que responder preguntas sobre dónde nació, su estatus migratorio o cómo entró a EE.UU. Diga: "Estoy ejerciendo mi derecho a guardar silencio."'
            }
        },
        {
            id: 'attorney',
            icon: '⚖️',
            title: { en: 'Right to an Attorney', es: 'Derecho a un Abogado' },
            body: {
                en: 'You have the right to speak with a lawyer before answering any questions. Say: "I want to speak with my lawyer." Do not sign anything without legal counsel.',
                es: 'Usted tiene derecho a hablar con un abogado antes de responder cualquier pregunta. Diga: "Quiero hablar con mi abogado." No firme nada sin asesoría legal.'
            }
        },
        {
            id: 'door',
            icon: '🚪',
            title: { en: 'If ICE Comes to Your Door', es: 'Si ICE Llega a Su Puerta' },
            body: {
                en: '<ul><li>You do NOT have to open the door unless they have a <strong>judicial warrant</strong> signed by a judge (not an ICE administrative warrant).</li><li>Ask them to slide the warrant under the door.</li><li>Do not open the door. Speak through the closed door.</li><li>Say: "I do not consent to entry."</li><li>Record badge numbers and names if possible.</li></ul>',
                es: '<ul><li>NO tiene que abrir la puerta a menos que tengan una <strong>orden judicial</strong> firmada por un juez (no una orden administrativa de ICE).</li><li>Pida que deslicen la orden por debajo de la puerta.</li><li>No abra la puerta. Hable a través de la puerta cerrada.</li><li>Diga: "No consiento a la entrada."</li><li>Registre números de placa y nombres si es posible.</li></ul>'
            }
        },
        {
            id: 'checkpoint',
            icon: '🛣️',
            title: { en: 'At a Checkpoint', es: 'En un Punto de Control' },
            body: {
                en: '<ul><li>You must stop if asked, but you DO NOT have to answer questions about your immigration status.</li><li>You DO NOT have to consent to a search of your vehicle.</li><li>Say: "I do not consent to a search. Am I free to go?"</li><li>Stay calm. Do not flee or resist.</li></ul>',
                es: '<ul><li>Debe detenerse si se lo piden, pero NO tiene que responder preguntas sobre su estatus migratorio.</li><li>NO tiene que consentir a una búsqueda de su vehículo.</li><li>Diga: "No consiento a una búsqueda. ¿Soy libre de irme?"</li><li>Mantenga la calma. No huya ni resista.</li></ul>'
            }
        },
        {
            id: 'workplace',
            icon: '🏢',
            title: { en: 'Rights at the Workplace', es: 'Derechos en el Lugar de Trabajo' },
            body: {
                en: '<ul><li>ICE cannot enter non-public areas of a workplace without a judicial warrant or employer consent.</li><li>You have the right to remain silent and ask for a lawyer.</li><li>Do not run. Stay calm.</li><li>If arrested, do not sign a voluntary departure form.</li><li>Remember: your employer cannot retaliate against you for exercising your rights.</li></ul>',
                es: '<ul><li>ICE no puede entrar a áreas no públicas del lugar de trabajo sin una orden judicial o consentimiento del empleador.</li><li>Tiene derecho a guardar silencio y pedir un abogado.</li><li>No corra. Mantenga la calma.</li><li>Si es arrestado, no firme un formulario de salida voluntaria.</li><li>Recuerde: su empleador no puede tomar represalias por ejercer sus derechos.</li></ul>'
            }
        }
    ];

    // Safe / known resource locations in NJ
    const SAFE_LOCATIONS = [
        {
            icon: '⚖️',
            name: { en: 'American Friends Service Committee NJ', es: 'American Friends Service Committee NJ' },
            addr: '89 Market St, Newark, NJ 07102',
            phone: '(973) 643-1924'
        },
        {
            icon: '🤝',
            name: { en: 'Wind of the Spirit — Immigrant Resource Center', es: 'Wind of the Spirit — Centro de Recursos para Inmigrantes' },
            addr: '60 South Fullerton Ave, Montclair, NJ 07042',
            phone: '(862) 262-8337'
        },
        {
            icon: '📋',
            name: { en: 'NJ Alliance for Immigrant Justice', es: 'Alianza NJ por la Justicia Inmigrante' },
            addr: 'Statewide — remote services available',
            phone: ''
        },
        {
            icon: '⚖️',
            name: { en: 'ACLU of New Jersey', es: 'ACLU de Nueva Jersey' },
            addr: 'P.O. Box 32159, Newark, NJ 07102',
            phone: '(973) 642-2084'
        },
        {
            icon: '🏛️',
            name: { en: 'Legal Services of New Jersey', es: 'Servicios Legales de Nueva Jersey' },
            addr: '100 Metroplex Dr #402, Edison, NJ 08817',
            phone: '1-888-576-5529'
        }
    ];

    const UI_STRINGS = {
        en: {
            emergencyMode: 'Emergency Mode',
            close: 'Close',
            offline: 'Offline — cached data',
            contacts: 'Emergency Contacts',
            addContact: 'Add Contact',
            namePlaceholder: 'Name',
            phonePlaceholder: 'Phone number',
            sendSMS: 'Quick SMS',
            legalAidBtn: 'I need legal assistance / Necesito asistencia legal',
            contactOrgBtn: 'Contact legal aid for me / Contacte asistencia legal por mí',
            customSMS: 'Send custom message',
            sendCustom: 'Send',
            knowYourRights: 'Know Your Rights / Conozca Sus Derechos',
            printRights: '🖨️ Print Rights Cards',
            safeLocations: 'Resources & Legal Aid',
            legalAidNumbers: 'Legal Aid Hotlines',
            cachedData: 'Cached Signal Data',
            noCachedData: 'No cached data available. Connect to network to load.',
            lastCached: 'Last cached',
            emergencyBtn: 'Emergency',
            call: 'Call',
            remove: '✕'
        },
        es: {
            emergencyMode: 'Modo de Emergencia',
            close: 'Cerrar',
            offline: 'Sin conexión — datos en caché',
            contacts: 'Contactos de Emergencia',
            addContact: 'Agregar Contacto',
            namePlaceholder: 'Nombre',
            phonePlaceholder: 'Número de teléfono',
            sendSMS: 'SMS Rápido',
            legalAidBtn: 'Necesito asistencia legal / I need legal assistance',
            contactOrgBtn: 'Contacte asistencia legal por mí / Contact legal aid for me',
            customSMS: 'Enviar mensaje personalizado',
            sendCustom: 'Enviar',
            knowYourRights: 'Conozca Sus Derechos / Know Your Rights',
            printRights: '🖨️ Imprimir Tarjetas de Derechos',
            safeLocations: 'Recursos y Asistencia Legal',
            legalAidNumbers: 'Líneas de Ayuda Legal',
            cachedData: 'Datos de Señal en Caché',
            noCachedData: 'No hay datos en caché disponibles. Conéctese a la red para cargar.',
            lastCached: 'Última caché',
            emergencyBtn: 'Emergencia',
            call: 'Llamar',
            remove: '✕'
        }
    };

    // =========================================================================
    // STATE
    // =========================================================================

    let db = null;
    let currentLang = 'en';
    let contacts = [];
    let isEmergencyActive = false;
    let overlayEl = null;

    // =========================================================================
    // IndexedDB — LOCAL-FIRST STORAGE
    // =========================================================================

    function openDB() {
        return new Promise(function (resolve, reject) {
            if (db) { resolve(db); return; }
            var req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = function (e) {
                var d = e.target.result;
                Object.keys(STORES).forEach(function (k) {
                    if (!d.objectStoreNames.contains(STORES[k])) {
                        d.createObjectStore(STORES[k]);
                    }
                });
            };
            req.onsuccess = function (e) { db = e.target.result; resolve(db); };
            req.onerror = function (e) { reject(e.target.error); };
        });
    }

    function dbPut(storeName, key, value) {
        return openDB().then(function (d) {
            return new Promise(function (resolve, reject) {
                var tx = d.transaction(storeName, 'readwrite');
                tx.objectStore(storeName).put(value, key);
                tx.oncomplete = function () { resolve(); };
                tx.onerror = function (e) { reject(e.target.error); };
            });
        });
    }

    function dbGet(storeName, key) {
        return openDB().then(function (d) {
            return new Promise(function (resolve, reject) {
                var tx = d.transaction(storeName, 'readonly');
                var req = tx.objectStore(storeName).get(key);
                req.onsuccess = function () { resolve(req.result); };
                req.onerror = function (e) { reject(e.target.error); };
            });
        });
    }

    // =========================================================================
    // DATA CACHING
    // =========================================================================

    function cacheHeatmapData(data) {
        return dbPut(STORES.heatmap, 'latest', { data: data, ts: Date.now() });
    }

    function cacheClusterData(data) {
        return dbPut(STORES.clusters, 'latest', { data: data, ts: Date.now() });
    }

    function cacheKYRContent() {
        return dbPut(STORES.kyr, 'content', { data: KYR_CONTENT, ts: Date.now() });
    }

    function getCachedHeatmap() {
        return dbGet(STORES.heatmap, 'latest');
    }

    function getCachedClusters() {
        return dbGet(STORES.clusters, 'latest');
    }

    function getCachedKYR() {
        return dbGet(STORES.kyr, 'content');
    }

    /**
     * Sync data from network — called when online. Caches whatever is currently
     * loaded in the main app's global state if available.
     */
    function syncFromApp() {
        try {
            // Cache current app data if available globally
            if (window.heatmapData) { cacheHeatmapData(window.heatmapData); }
            if (window.clusterData) { cacheClusterData(window.clusterData); }
            // Always cache KYR (it's embedded)
            cacheKYRContent();
        } catch (e) {
            // Fail silently — offline caching is best-effort
        }
    }

    // =========================================================================
    // CONTACTS — localStorage
    // =========================================================================

    function initEmergencyContacts() {
        try {
            var raw = localStorage.getItem(CONTACTS_KEY);
            contacts = raw ? JSON.parse(raw) : [];
        } catch (e) {
            contacts = [];
        }
        return contacts;
    }

    function saveContacts() {
        try {
            localStorage.setItem(CONTACTS_KEY, JSON.stringify(contacts));
        } catch (e) { /* storage full or unavailable */ }
    }

    function addEmergencyContact(name, phone) {
        if (!name || !phone) return false;
        var cleaned = phone.replace(/[^\d+\-() ]/g, '');
        if (cleaned.length < 7) return false;
        contacts.push({ name: name.trim(), phone: cleaned.trim(), id: Date.now() });
        saveContacts();
        return true;
    }

    function removeEmergencyContact(id) {
        contacts = contacts.filter(function (c) { return c.id !== id; });
        saveContacts();
    }

    // =========================================================================
    // SMS INTEGRATION
    // =========================================================================

    function buildSMSURI(phones, message) {
        // Normalize to array
        var recipients = Array.isArray(phones) ? phones : [phones];
        var cleanPhones = recipients.map(function (p) {
            return p.replace(/[^\d+]/g, '');
        }).filter(Boolean);

        if (cleanPhones.length === 0) return null;

        // sms: URI scheme — works on iOS and Android
        var uri = 'sms:' + cleanPhones.join(',');
        if (message) {
            // iOS uses &body=, Android uses ?body= — use ? for broadest compat
            uri += '?body=' + encodeURIComponent(message);
        }
        return uri;
    }

    function sendEmergencySMS(message) {
        if (contacts.length === 0) return;
        var phones = contacts.map(function (c) { return c.phone; });
        var uri = buildSMSURI(phones, message);
        if (uri) {
            window.location.href = uri;
        }
    }

    function sendSMSToPhone(phone, message) {
        var uri = buildSMSURI(phone, message);
        if (uri) { window.location.href = uri; }
    }

    // =========================================================================
    // LANGUAGE
    // =========================================================================

    function t(key) {
        return (UI_STRINGS[currentLang] || UI_STRINGS.en)[key] || key;
    }

    function setLang(lang) {
        currentLang = (lang === 'es') ? 'es' : 'en';
        try { localStorage.setItem(LANG_KEY, currentLang); } catch (e) { /* */ }
        if (isEmergencyActive && overlayEl) { renderOverlayContent(); }
    }

    function loadLang() {
        try {
            var saved = localStorage.getItem(LANG_KEY);
            if (saved === 'es' || saved === 'en') { currentLang = saved; }
            // Also check main app lang selector
            var sel = document.getElementById('lang-select');
            if (sel && sel.value === 'es') { currentLang = 'es'; }
        } catch (e) { /* */ }
    }

    // =========================================================================
    // RENDER — Know Your Rights
    // =========================================================================

    function renderKnowYourRights(container) {
        var wrap = container || document.createElement('div');
        wrap.className = 'kyr-cards';
        wrap.setAttribute('role', 'list');
        wrap.setAttribute('aria-label', t('knowYourRights'));

        var html = '';
        KYR_CONTENT.forEach(function (card) {
            html += '<article class="kyr-card" role="listitem">';
            html += '<div class="kyr-card__title">' + card.icon + ' ' + escHTML(card.title[currentLang] || card.title.en) + '</div>';
            html += '<div class="kyr-card__body">';
            html += card.body[currentLang] || card.body.en;
            // Always show other language as subtitle
            var otherLang = currentLang === 'en' ? 'es' : 'en';
            html += '<span class="kyr-es">' + (card.body[otherLang] || '') + '</span>';
            html += '</div></article>';
        });
        wrap.innerHTML = html;
        return wrap;
    }

    // =========================================================================
    // RENDER — FULL EMERGENCY OVERLAY
    // =========================================================================

    function activateEmergencyMode() {
        if (isEmergencyActive) return;
        isEmergencyActive = true;

        // Create overlay
        overlayEl = document.createElement('div');
        overlayEl.className = 'heat-emergency-overlay';
        overlayEl.setAttribute('role', 'dialog');
        overlayEl.setAttribute('aria-modal', 'true');
        overlayEl.setAttribute('aria-label', t('emergencyMode'));

        renderOverlayContent();
        document.body.appendChild(overlayEl);

        // Prevent background scroll
        document.body.style.overflow = 'hidden';

        // Trap focus
        overlayEl.focus();

        // Cache KYR on activation
        cacheKYRContent().catch(function () { /* best effort */ });
    }

    function deactivateEmergencyMode() {
        if (!isEmergencyActive) return;
        isEmergencyActive = false;
        if (overlayEl && overlayEl.parentNode) {
            overlayEl.parentNode.removeChild(overlayEl);
        }
        overlayEl = null;
        document.body.style.overflow = '';
    }

    function renderOverlayContent() {
        if (!overlayEl) return;

        var isOffline = !navigator.onLine;

        var html = '';

        // Header
        html += '<div class="emergency-header">';
        html += '<h1 class="emergency-header__title">🆘 ' + t('emergencyMode') + '</h1>';
        html += '<span class="emergency-offline-badge ' + (isOffline ? 'visible' : '') + '">' + t('offline') + '</span>';
        html += '<button class="emergency-header__lang" id="em-lang-toggle" title="Toggle EN/ES">' + (currentLang === 'en' ? 'ES' : 'EN') + '</button>';
        html += '<button class="emergency-header__close" id="em-close" aria-label="' + t('close') + '">✕</button>';
        html += '</div>';

        // Body
        html += '<div class="emergency-body">';

        // === Quick Actions ===
        html += '<div class="emergency-actions">';
        html += '<a href="tel:18885765529" class="emergency-action-btn emergency-action-btn--primary">';
        html += '<span class="action-icon">📞</span>';
        html += '<span class="action-text">Legal Services of NJ Hotline<small>1-888-576-5529</small></span>';
        html += '</a>';
        html += '<a href="tel:19736421540" class="emergency-action-btn emergency-action-btn--primary">';
        html += '<span class="action-icon">⚖️</span>';
        html += '<span class="action-text">ACLU NJ Legal Intake<small>(973) 642-1540</small></span>';
        html += '</a>';
        html += '</div>';

        // === Emergency Contacts ===
        html += '<section class="emergency-section">';
        html += '<h2 class="emergency-section__title">' + t('contacts') + '</h2>';
        html += '<ul class="emergency-contact-list" id="em-contact-list">';
        contacts.forEach(function (c) {
            html += '<li class="emergency-contact-item" data-id="' + c.id + '">';
            html += '<span class="emergency-contact-item__name">' + escHTML(c.name) + '</span>';
            html += '<a href="tel:' + escAttr(c.phone) + '" class="emergency-contact-item__phone" title="' + t('call') + ' ' + escAttr(c.name) + '">' + escHTML(c.phone) + '</a>';
            html += '<button class="emergency-contact-item__remove em-remove-contact" data-id="' + c.id + '" aria-label="' + t('remove') + ' ' + escAttr(c.name) + '">' + t('remove') + '</button>';
            html += '</li>';
        });
        html += '</ul>';
        html += '<div class="emergency-add-contact">';
        html += '<input type="text" id="em-contact-name" placeholder="' + t('namePlaceholder') + '" autocomplete="name">';
        html += '<input type="tel" id="em-contact-phone" placeholder="' + t('phonePlaceholder') + '" autocomplete="tel">';
        html += '<button id="em-add-contact">' + t('addContact') + '</button>';
        html += '</div>';
        html += '</section>';

        // === Quick SMS ===
        html += '<section class="emergency-section">';
        html += '<h2 class="emergency-section__title">' + t('sendSMS') + '</h2>';
        html += '<div class="emergency-sms-templates">';
        html += '<button class="emergency-sms-btn" data-template="legalAid">';
        html += SMS_TEMPLATES.legalAid.en + '<small>' + SMS_TEMPLATES.legalAid.es + '</small>';
        html += '</button>';
        html += '<button class="emergency-sms-btn" data-template="contactOrg">';
        html += SMS_TEMPLATES.contactOrg.en + '<small>' + SMS_TEMPLATES.contactOrg.es + '</small>';
        html += '</button>';
        html += '</div>';
        html += '<textarea class="emergency-custom-sms" id="em-custom-msg" placeholder="' + SMS_TEMPLATES.customPlaceholder[currentLang] + '"></textarea>';
        html += '<button class="emergency-sms-btn" id="em-send-custom" style="margin-top:8px;">' + t('customSMS') + '</button>';
        html += '</section>';

        // === Know Your Rights ===
        html += '<section class="emergency-section emergency-section--kyr">';
        html += '<h2 class="emergency-section__title">' + t('knowYourRights') + '</h2>';
        html += '<button class="emergency-sms-btn kyr-print-btn" id="em-print-kyr" style="margin-bottom:12px;">' + t('printRights') + '</button>';
        html += '<div id="em-kyr-cards"></div>';
        html += '</section>';

        // === Safe Locations / Legal Aid ===
        html += '<section class="emergency-section">';
        html += '<h2 class="emergency-section__title">' + t('safeLocations') + '</h2>';
        html += '<div class="emergency-locations">';
        SAFE_LOCATIONS.forEach(function (loc) {
            html += '<div class="emergency-location-item">';
            html += '<span class="emergency-location-item__icon">' + loc.icon + '</span>';
            html += '<div class="emergency-location-item__info">';
            html += '<div class="emergency-location-item__name">' + escHTML(loc.name[currentLang] || loc.name.en) + '</div>';
            html += '<div class="emergency-location-item__addr">' + escHTML(loc.addr) + '</div>';
            html += '</div>';
            if (loc.phone) {
                html += '<a href="tel:' + escAttr(loc.phone.replace(/[^\d+]/g, '')) + '" class="emergency-contact-item__phone" title="' + t('call') + '">' + escHTML(loc.phone) + '</a>';
            }
            html += '</div>';
        });
        html += '</div>';
        html += '</section>';

        html += '</div>'; // end .emergency-body

        overlayEl.innerHTML = html;

        // Render KYR cards into container
        var kyrContainer = overlayEl.querySelector('#em-kyr-cards');
        if (kyrContainer) { renderKnowYourRights(kyrContainer); }

        // Bind events
        bindOverlayEvents();
    }

    function bindOverlayEvents() {
        if (!overlayEl) return;

        // Close
        var closeBtn = overlayEl.querySelector('#em-close');
        if (closeBtn) { closeBtn.addEventListener('click', deactivateEmergencyMode); }

        // Language toggle
        var langBtn = overlayEl.querySelector('#em-lang-toggle');
        if (langBtn) {
            langBtn.addEventListener('click', function () {
                setLang(currentLang === 'en' ? 'es' : 'en');
            });
        }

        // Add contact
        var addBtn = overlayEl.querySelector('#em-add-contact');
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                var nameEl = overlayEl.querySelector('#em-contact-name');
                var phoneEl = overlayEl.querySelector('#em-contact-phone');
                if (nameEl && phoneEl) {
                    var ok = addEmergencyContact(nameEl.value, phoneEl.value);
                    if (ok) {
                        nameEl.value = '';
                        phoneEl.value = '';
                        renderOverlayContent();
                    }
                }
            });
        }

        // Remove contacts
        var removeBtns = overlayEl.querySelectorAll('.em-remove-contact');
        removeBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = parseInt(btn.getAttribute('data-id'), 10);
                removeEmergencyContact(id);
                renderOverlayContent();
            });
        });

        // SMS templates
        var smsBtns = overlayEl.querySelectorAll('.emergency-sms-btn[data-template]');
        smsBtns.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var tpl = btn.getAttribute('data-template');
                if (SMS_TEMPLATES[tpl]) {
                    var msg = SMS_TEMPLATES[tpl].en + ' / ' + SMS_TEMPLATES[tpl].es;
                    sendEmergencySMS(msg);
                }
            });
        });

        // Custom SMS
        var sendCustom = overlayEl.querySelector('#em-send-custom');
        if (sendCustom) {
            sendCustom.addEventListener('click', function () {
                var ta = overlayEl.querySelector('#em-custom-msg');
                if (ta && ta.value.trim()) {
                    sendEmergencySMS(ta.value.trim());
                }
            });
        }

        // Print KYR
        var printBtn = overlayEl.querySelector('#em-print-kyr');
        if (printBtn) {
            printBtn.addEventListener('click', function () {
                window.print();
            });
        }

        // Escape key closes
        overlayEl.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { deactivateEmergencyMode(); }
        });
    }

    // =========================================================================
    // EMERGENCY BUTTON — injected into page
    // =========================================================================

    function injectEmergencyButton() {
        if (document.querySelector('.heat-emergency-btn')) return;
        var btn = document.createElement('button');
        btn.className = 'heat-emergency-btn';
        btn.setAttribute('aria-label', t('emergencyBtn'));
        btn.setAttribute('title', t('emergencyBtn'));
        btn.addEventListener('click', activateEmergencyMode);
        document.body.appendChild(btn);
    }

    // =========================================================================
    // NETWORK STATUS — SYNC
    // =========================================================================

    function setupNetworkListeners() {
        window.addEventListener('online', function () {
            syncFromApp();
            // Update offline badge if overlay open
            if (overlayEl) {
                var badge = overlayEl.querySelector('.emergency-offline-badge');
                if (badge) { badge.classList.remove('visible'); }
            }
        });

        window.addEventListener('offline', function () {
            if (overlayEl) {
                var badge = overlayEl.querySelector('.emergency-offline-badge');
                if (badge) { badge.classList.add('visible'); }
            }
        });
    }

    // =========================================================================
    // UTILITIES
    // =========================================================================

    function escHTML(str) {
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str || ''));
        return div.innerHTML;
    }

    function escAttr(str) {
        return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // =========================================================================
    // INIT
    // =========================================================================

    function init() {
        loadLang();
        initEmergencyContacts();

        // Open IndexedDB early
        openDB().then(function () {
            // Initial sync if online
            if (navigator.onLine) { syncFromApp(); }
        }).catch(function () {
            // IndexedDB unavailable — degrade gracefully
        });

        // Inject button after DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function () {
                injectEmergencyButton();
            });
        } else {
            injectEmergencyButton();
        }

        setupNetworkListeners();
    }

    // =========================================================================
    // PUBLIC API — global HeatEmergency
    // =========================================================================

    var HeatEmergency = {
        init: init,
        activate: activateEmergencyMode,
        deactivate: deactivateEmergencyMode,
        isActive: function () { return isEmergencyActive; },

        // Contacts
        initEmergencyContacts: initEmergencyContacts,
        addEmergencyContact: addEmergencyContact,
        removeEmergencyContact: removeEmergencyContact,
        getContacts: function () { return contacts.slice(); },

        // SMS
        sendEmergencySMS: sendEmergencySMS,
        sendSMSToPhone: sendSMSToPhone,
        getSMSTemplates: function () { return SMS_TEMPLATES; },

        // Know Your Rights
        renderKnowYourRights: renderKnowYourRights,
        getKYRContent: function () { return KYR_CONTENT; },

        // Cache / offline
        cacheHeatmapData: cacheHeatmapData,
        cacheClusterData: cacheClusterData,
        getCachedHeatmap: getCachedHeatmap,
        getCachedClusters: getCachedClusters,
        syncFromApp: syncFromApp,

        // Language
        setLang: setLang,
        getLang: function () { return currentLang; }
    };

    window.HeatEmergency = HeatEmergency;

    // Auto-init
    init();

})();
