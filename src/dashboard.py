import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Data directory handling
def get_data_dir():
    """Return the data directory path, creating it if needed"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

# Database connection
def get_db_connection():
    db_path = os.path.join(get_data_dir(), 'domains.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/domains')
def get_domains():
    # Get query parameters for filtering and sorting
    sort_by = request.args.get('sort_by', 'average_score')
    sort_dir = request.args.get('sort_dir', 'desc')
    min_score = request.args.get('min_score', 0, type=float)
    tld_filter = request.args.get('tld', '')
    search = request.args.get('search', '')
    
    # Connect to database
    conn = get_db_connection()
    
    # Build the query dynamically
    query = """
        SELECT domain, memorability, pronunciation, visual_appeal, brandability, average_score, 
               price, price_type, error
        FROM domain_results
        WHERE average_score IS NOT NULL
    """
    
    params = []
    
    # Add filters
    if min_score > 0:
        query += " AND average_score >= ?"
        params.append(min_score)
    
    if tld_filter:
        query += " AND domain LIKE '%." + tld_filter + "'"
    
    if search:
        query += " AND domain LIKE ?"
        params.append(f"%{search}%")
    
    # Add sorting
    if sort_by in ['domain', 'memorability', 'pronunciation', 'visual_appeal', 'brandability', 'average_score', 'price']:
        query += f" ORDER BY {sort_by} {'DESC' if sort_dir.lower() == 'desc' else 'ASC'}"
    
    # Execute query
    cursor = conn.execute(query, params)
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(data)

@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    
    # Get total domains
    total = conn.execute("SELECT COUNT(*) FROM domain_results").fetchone()[0]
    
    # Get domains by TLD
    tlds_query = """
        SELECT 
            SUBSTR(domain, INSTR(domain, '.') + 1) as tld,
            COUNT(*) as count 
        FROM domain_results 
        GROUP BY SUBSTR(domain, INSTR(domain, '.') + 1)
    """
    tlds = [dict(row) for row in conn.execute(tlds_query).fetchall()]
    
    # Get average scores
    avg_scores = conn.execute("""
        SELECT 
            AVG(memorability) as avg_memorability,
            AVG(pronunciation) as avg_pronunciation,
            AVG(visual_appeal) as avg_visual_appeal,
            AVG(brandability) as avg_brandability,
            AVG(average_score) as avg_score,
            AVG(price) as avg_price
        FROM domain_results
        WHERE average_score IS NOT NULL
    """).fetchone()
    
    # Get price statistics
    price_stats = conn.execute("""
        SELECT 
            price_type, 
            COUNT(*) as count,
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price
        FROM domain_results
        WHERE price IS NOT NULL
        GROUP BY price_type
    """).fetchall()
    
    price_data = [dict(row) for row in price_stats]
    
    conn.close()
    
    return jsonify({
        'total': total,
        'tlds': tlds,
        'averages': dict(avg_scores),
        'price_stats': price_data
    })

# Create templates directory and template files
def create_templates():
    """
    Create the templates directory and HTML template files for the Flask app.
    Ensures templates are created in the correct location relative to the script.
    """
    # Get the directory where the dashboard.py script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create templates directory in the Flask default location
    templates_dir = os.path.join(script_dir, 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create the index.html template file
    with open(os.path.join(templates_dir, 'index.html'), 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Domain Scoring Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --text-color: #c9d1d9;
            --border-color: #30363d;
            --highlight: #6b7280;
            --highlight-light: #8c98a8;
            --accent-color: #64748b;
            --danger-color: #9b1c1c;
            --warning-color: #92400e;
            --info-color: #1e429f;
            --success-color: #065f46;
            --active-row-bg: rgba(108, 117, 125, 0.3);
        }
        
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Courier New', 'Andale Mono', monospace;
        }
        
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .card-title {
            font-weight: 700;
            color: #fff;
            letter-spacing: -0.5px;
        }
        
        .table {
            color: var(--text-color);
            border-color: var(--border-color);
        }
        
        .table th {
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 1px;
        }
        
        thead {
            background-color: var(--card-bg);
        }
        
        tbody tr:hover {
            background-color: rgba(108, 117, 125, 0.1) !important;
        }
        
        .btn-primary {
            background-color: var(--highlight);
            border-color: var(--highlight);
            border-radius: 3px;
        }
        
        .btn-primary:hover {
            background-color: var(--highlight-light);
            border-color: var(--highlight-light);
        }
        
        .btn-outline-secondary {
            color: var(--text-color);
            border-color: var(--border-color);
            border-radius: 3px;
        }
        
        .btn-outline-secondary:hover {
            background-color: var(--border-color);
            color: white;
        }
        
        .form-control, .form-select {
            background-color: #0d1117;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            border-radius: 3px;
            font-family: 'Courier New', 'Andale Mono', monospace;
        }
        
        .form-control:focus, .form-select:focus {
            background-color: #0d1117;
            color: var(--text-color);
            border-color: var(--highlight);
            box-shadow: 0 0 0 0.25rem rgba(108, 117, 125, 0.25);
        }
        
        .dropdown-menu {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 3px;
        }
        
        .dropdown-item {
            color: var(--text-color);
        }
        
        .dropdown-item:hover {
            background-color: var(--highlight);
            color: white;
        }
        
        .domain-item {
            cursor: pointer;
        }
        
        .sortable {
            cursor: pointer;
            user-select: none;
        }
        
        .sort-icon {
            display: inline-block;
            width: 0;
            height: 0;
            margin-left: 0.3em;
            vertical-align: middle;
            content: "";
            border-top: 0.3em solid;
            border-right: 0.3em solid transparent;
            border-bottom: 0;
            border-left: 0.3em solid transparent;
        }
        
        .sort-icon.asc {
            transform: rotate(180deg);
        }
        
        .badge {
            font-weight: 500;
            font-size: 0.8em;
            border-radius: 3px;
        }
        
        .bg-success { background-color: var(--success-color) !important; }
        .bg-info { background-color: var(--info-color) !important; }
        .bg-warning { background-color: var(--warning-color) !important; }
        .bg-danger { background-color: var(--danger-color) !important; }
        .bg-premium { background-color: #6f42c1 !important; }
        .bg-standard { background-color: #20c997 !important; }
        .bg-taken { background-color: #6c757d !important; }
        
        .score-badge {
            width: 2.2em;
            display: inline-block;
            text-align: center;
            font-weight: bold;
        }
        
        .price-badge {
            min-width: 3.5em;
            display: inline-block;
            text-align: center;
            font-weight: bold;
        }
        
        .alert-dark {
            background-color: #1c2128;
            border-color: var(--border-color);
            color: var(--text-color);
            border-radius: 3px;
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-color);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--highlight);
        }
        
        /* Make table more minimal */
        .table tbody tr {
            border-left: 2px solid transparent;
            transition: all 0.2s ease;
        }
        
        .table tbody tr:hover {
            border-left: 2px solid var(--highlight);
        }
        
        /* Fix for highlighted rows - ensure text remains visible */
        .table-active {
            border-left: 2px solid var(--accent-color) !important;
            background-color: var(--active-row-bg) !important;
            color: var(--text-color) !important;
        }
        
        .table-active td {
            color: var(--text-color) !important;
        }
        
        .table-active .badge {
            color: white !important;
        }
        
        /* Simpler card title */
        .card-title {
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            margin-bottom: 12px;
        }
        
        /* Price card */
        .price-card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            margin-top: 10px;
        }
        
        .price-title {
            border-bottom: 1px solid var(--border-color);
            padding: 0.75rem 1.25rem;
            font-weight: 600;
        }
        
        .price-content {
            padding: 0.75rem 1.25rem;
        }
        
        /* No data message */
        .no-data {
            padding: 2rem;
            text-align: center;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="row mb-4">
            <div class="col">
                <h1 class="h3">DOMAIN SCORING DASHBOARD <span class="text-muted" style="font-size: 0.7em; opacity: 0.7;">v1.0</span></h1>
                <p class="text-muted">AI evaluation of domain name quality</p>
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card mb-3">
                    <div class="card-body">
                        <h5 class="card-title">STATS</h5>
                        <div id="stats-container">
                            <p class="mb-1">Total domains: <span id="total-domains" class="float-end">-</span></p>
                            <p class="mb-1">Avg score: <span id="avg-score" class="float-end">-</span></p>
                            <p class="mb-1">Priced domains: <span id="priced-domains" class="float-end">-</span></p>
                        </div>
                    </div>
                </div>
                
                <div class="card mb-3">
                    <div class="card-body">
                        <h5 class="card-title">FILTERS</h5>
                        <div class="mb-3">
                            <label for="search" class="form-label">Search</label>
                            <input type="text" class="form-control" id="search" placeholder="Search domains...">
                        </div>
                        <div class="mb-3">
                            <label for="tld-filter" class="form-label">TLD</label>
                            <select class="form-select" id="tld-filter">
                                <option value="">All TLDs</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label for="min-score" class="form-label">Min. Average Score</label>
                            <input type="range" class="form-range" min="0" max="10" step="0.5" value="0" id="min-score">
                            <div class="d-flex justify-content-between">
                                <small>0</small>
                                <small id="min-score-value">0</small>
                                <small>10</small>
                            </div>
                        </div>
                        <button id="apply-filters" class="btn btn-primary w-100">APPLY FILTERS</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">TLD DISTRIBUTION</h5>
                        <div id="tld-container">
                            <div class="text-center py-2">Loading...</div>
                        </div>
                    </div>
                </div>
                
                <div class="card mt-3">
                    <div class="card-body">
                        <h5 class="card-title">PRICING STATS</h5>
                        <div id="pricing-container">
                            <div class="text-center py-2">Loading...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-9">
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="card-title mb-0">DOMAIN RESULTS</h5>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" id="export-dropdown" data-bs-toggle="dropdown" aria-expanded="false">
                                    EXPORT
                                </button>
                                <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="export-dropdown">
                                    <li><a class="dropdown-item" href="#" id="export-csv">CSV</a></li>
                                    <li><a class="dropdown-item" href="#" id="export-json">JSON</a></li>
                                </ul>
                            </div>
                        </div>
                        
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th class="sortable" data-sort="domain">DOMAIN <span class="sort-icon"></span></th>
                                        <th class="sortable" data-sort="memorability">MEM <span class="sort-icon"></span></th>
                                        <th class="sortable" data-sort="pronunciation">PRON <span class="sort-icon"></span></th>
                                        <th class="sortable" data-sort="visual_appeal">VIS <span class="sort-icon"></span></th>
                                        <th class="sortable" data-sort="brandability">BRAND <span class="sort-icon"></span></th>
                                        <th class="sortable" data-sort="average_score">AVG <span class="sort-icon"></span></th>
                                        <th class="sortable" data-sort="price">PRICE <span class="sort-icon"></span></th>
                                    </tr>
                                </thead>
                                <tbody id="domains-table">
                                    <tr>
                                        <td colspan="7" class="text-center">Loading data...</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        
                        <div id="domain-details" class="alert alert-dark mt-3 d-none">
                            <h5 id="detail-domain" class="mb-3">Domain Details</h5>
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <div class="card bg-dark">
                                        <div class="card-body p-3">
                                            <h6 class="card-title" style="border-bottom: none; padding-bottom: 0;">MEMORABILITY <span id="detail-memorability" class="float-end score-badge">-</span></h6>
                                            <p class="card-text small mt-2">How easy it is to remember the domain name</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card bg-dark">
                                        <div class="card-body p-3">
                                            <h6 class="card-title" style="border-bottom: none; padding-bottom: 0;">PRONUNCIATION <span id="detail-pronunciation" class="float-end score-badge">-</span></h6>
                                            <p class="card-text small mt-2">How easily the domain can be pronounced</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card bg-dark">
                                        <div class="card-body p-3">
                                            <h6 class="card-title" style="border-bottom: none; padding-bottom: 0;">VISUAL APPEAL <span id="detail-visual_appeal" class="float-end score-badge">-</span></h6>
                                            <p class="card-text small mt-2">How attractive the domain looks as text</p>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="card bg-dark">
                                        <div class="card-body p-3">
                                            <h6 class="card-title" style="border-bottom: none; padding-bottom: 0;">BRANDABILITY <span id="detail-brandability" class="float-end score-badge">-</span></h6>
                                            <p class="card-text small mt-2">Potential as a strong brand name</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="price-card mt-3" id="price-details">
                                <div class="price-title">PRICING</div>
                                <div class="price-content">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <p class="mb-1">Price: <span id="detail-price" class="float-end">-</span></p>
                                        </div>
                                        <div class="col-md-6">
                                            <p class="mb-1">Type: <span id="detail-price-type" class="float-end">-</span></p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // State
            let domainsData = [];
            let currentSort = {
                column: 'average_score',
                direction: 'desc'
            };
            let filters = {
                search: '',
                tld: '',
                minScore: 0
            };
            
            // Elements
            const domainsTable = document.getElementById('domains-table');
            const searchInput = document.getElementById('search');
            const tldFilter = document.getElementById('tld-filter');
            const minScoreSlider = document.getElementById('min-score');
            const minScoreValue = document.getElementById('min-score-value');
            const applyFiltersBtn = document.getElementById('apply-filters');
            const domainDetails = document.getElementById('domain-details');
            const exportCsvBtn = document.getElementById('export-csv');
            const exportJsonBtn = document.getElementById('export-json');
            
            // Fetch initial data
            fetchDomains();
            fetchStats();
            
            // Event listeners
            applyFiltersBtn.addEventListener('click', fetchDomains);
            minScoreSlider.addEventListener('input', function() {
                minScoreValue.textContent = this.value;
                filters.minScore = parseFloat(this.value);
            });
            
            document.querySelectorAll('.sortable').forEach(header => {
                header.addEventListener('click', function() {
                    const column = this.dataset.sort;
                    const isCurrentSort = currentSort.column === column;
                    currentSort.direction = isCurrentSort && currentSort.direction === 'asc' ? 'desc' : 'asc';
                    currentSort.column = column;
                    
                    // Update sorting icons
                    document.querySelectorAll('.sort-icon').forEach(icon => {
                        icon.className = 'sort-icon';
                    });
                    
                    const sortIcon = this.querySelector('.sort-icon');
                    sortIcon.classList.add(currentSort.direction);
                    
                    fetchDomains();
                });
            });
            
            exportCsvBtn.addEventListener('click', exportCsv);
            exportJsonBtn.addEventListener('click', exportJson);
            
            // Functions
            function fetchDomains() {
                filters.search = searchInput.value.trim();
                filters.tld = tldFilter.value;
                filters.minScore = parseFloat(minScoreSlider.value);
                
                const params = new URLSearchParams({
                    sort_by: currentSort.column,
                    sort_dir: currentSort.direction,
                    min_score: filters.minScore,
                    tld: filters.tld,
                    search: filters.search
                });
                
                fetch(`/api/domains?${params}`)
                    .then(response => response.json())
                    .then(data => {
                        domainsData = data;
                        renderTable(data);
                    })
                    .catch(error => {
                        console.error('Error fetching domains:', error);
                        domainsTable.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error loading data. Please try again.</td></tr>`;
                    });
            }
            
            function fetchStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('total-domains').textContent = data.total;
                        document.getElementById('avg-score').textContent = data.averages.avg_score 
                            ? parseFloat(data.averages.avg_score).toFixed(1)
                            : '-';
                        
                        // Count priced domains
                        let pricedDomains = 0;
                        if (data.price_stats) {
                            data.price_stats.forEach(stat => {
                                if (stat.price_type !== 'Error') {
                                    pricedDomains += stat.count;
                                }
                            });
                        }
                        document.getElementById('priced-domains').textContent = pricedDomains;
                        
                        // Populate TLD filter
                        tldFilter.innerHTML = '<option value="">All TLDs</option>';
                        data.tlds.forEach(tld => {
                            const option = document.createElement('option');
                            option.value = tld.tld;
                            option.textContent = `.${tld.tld} (${tld.count})`;
                            tldFilter.appendChild(option);
                        });
                        
                        // Render TLD distribution
                        const tldContainer = document.getElementById('tld-container');
                        tldContainer.innerHTML = '';
                        
                        data.tlds.forEach(tld => {
                            const tldItem = document.createElement('div');
                            tldItem.className = 'd-flex justify-content-between mb-1';
                            tldItem.innerHTML = `
                                <span>.${tld.tld}</span>
                                <span class="badge bg-secondary">${tld.count}</span>
                            `;
                            tldContainer.appendChild(tldItem);
                        });
                        
                        // Render pricing stats
                        const pricingContainer = document.getElementById('pricing-container');
                        pricingContainer.innerHTML = '';
                        
                        if (data.price_stats && data.price_stats.length > 0) {
                            data.price_stats.forEach(stat => {
                                if (stat.price_type && stat.count) {
                                    const priceItem = document.createElement('div');
                                    priceItem.className = 'd-flex justify-content-between mb-1';
                                    const priceLabel = stat.price_type.charAt(0).toUpperCase() + stat.price_type.slice(1);
                                    priceItem.innerHTML = `
                                        <span>${priceLabel}</span>
                                        <span class="badge bg-${stat.price_type.toLowerCase()}">${stat.count}</span>
                                    `;
                                    pricingContainer.appendChild(priceItem);
                                    
                                    if (stat.avg_price) {
                                        const avgPriceItem = document.createElement('div');
                                        avgPriceItem.className = 'small text-muted mb-2';
                                        avgPriceItem.innerHTML = `Avg: $${parseFloat(stat.avg_price).toFixed(2)}`;
                                        pricingContainer.appendChild(avgPriceItem);
                                    }
                                }
                            });
                        } else {
                            pricingContainer.innerHTML = '<div class="text-center py-2">No pricing data</div>';
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching stats:', error);
                    });
            }
            
            function renderTable(data) {
                if (data.length === 0) {
                    domainsTable.innerHTML = `<tr><td colspan="7" class="text-center">No domains found matching your criteria.</td></tr>`;
                    return;
                }
                
                domainsTable.innerHTML = '';
                
                data.forEach((domain, index) => {
                    const row = document.createElement('tr');
                    row.className = 'domain-item';
                    row.dataset.index = index;
                    
                    const getScoreClass = (score) => {
                        if (!score) return 'secondary';
                        if (score >= 8) return 'success';
                        if (score >= 6) return 'info';
                        if (score >= 4) return 'warning';
                        return 'danger';
                    };
                    
                    const getPriceClass = (priceType) => {
                        if (!priceType) return 'secondary';
                        if (priceType === 'Premium') return 'premium';
                        if (priceType === 'Standard') return 'standard';
                        if (priceType === 'Taken') return 'taken';
                        return 'secondary';
                    };
                    
                    const formatScore = (score) => {
                        return score ? parseFloat(score).toFixed(1) : '-';
                    };
                    
                    const formatPrice = (price, price_type) => {
                        if (!price_type) return '-';
                        if (price_type === 'Taken') return 'Taken';
                        if (price_type === 'Error') return 'Error';
                        return price ? `$${parseFloat(price).toFixed(2)}` : '-';
                    };
                    
                    row.innerHTML = `
                        <td>${domain.domain}</td>
                        <td><span class="badge bg-${getScoreClass(domain.memorability)}">${formatScore(domain.memorability)}</span></td>
                        <td><span class="badge bg-${getScoreClass(domain.pronunciation)}">${formatScore(domain.pronunciation)}</span></td>
                        <td><span class="badge bg-${getScoreClass(domain.visual_appeal)}">${formatScore(domain.visual_appeal)}</span></td>
                        <td><span class="badge bg-${getScoreClass(domain.brandability)}">${formatScore(domain.brandability)}</span></td>
                        <td><span class="badge bg-${getScoreClass(domain.average_score)}">${formatScore(domain.average_score)}</span></td>
                        <td><span class="badge bg-${getPriceClass(domain.price_type)}">${formatPrice(domain.price, domain.price_type)}</span></td>
                    `;
                    
                    row.addEventListener('click', () => showDomainDetails(index));
                    domainsTable.appendChild(row);
                });
            }
            
            function showDomainDetails(index) {
                const domain = domainsData[index];
                
                document.getElementById('detail-domain').textContent = domain.domain;
                document.getElementById('detail-memorability').textContent = domain.memorability ? parseFloat(domain.memorability).toFixed(1) : '-';
                document.getElementById('detail-pronunciation').textContent = domain.pronunciation ? parseFloat(domain.pronunciation).toFixed(1) : '-';
                document.getElementById('detail-visual_appeal').textContent = domain.visual_appeal ? parseFloat(domain.visual_appeal).toFixed(1) : '-';
                document.getElementById('detail-brandability').textContent = domain.brandability ? parseFloat(domain.brandability).toFixed(1) : '-';
                
                // Set price details
                document.getElementById('detail-price').textContent = domain.price ? `$${parseFloat(domain.price).toFixed(2)}` : '-';
                document.getElementById('detail-price-type').textContent = domain.price_type || '-';
                
                // Show/hide price details
                const priceDetails = document.getElementById('price-details');
                priceDetails.style.display = domain.price_type ? 'block' : 'none';
                
                // Highlight selected row
                document.querySelectorAll('.domain-item').forEach(row => {
                    row.classList.remove('table-active');
                });
                document.querySelector(`.domain-item[data-index="${index}"]`).classList.add('table-active');
                
                domainDetails.classList.remove('d-none');
            }
            
            function downloadFile(content, filename, type) {
                const blob = new Blob([content], { type });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
            
            function exportCsv() {
                const headers = ['domain', 'memorability', 'pronunciation', 'visual_appeal', 'brandability', 'average_score', 'price', 'price_type'];
                const csvContent = [
                    headers.join(','),
                    ...domainsData.map(domain => 
                        headers.map(key => domain[key] !== null ? domain[key] : '').join(',')
                    )
                ].join('\n');
                
                downloadFile(csvContent, 'domain-scores.csv', 'text/csv');
            }
            
            function exportJson() {
                const jsonContent = JSON.stringify(domainsData, null, 2);
                downloadFile(jsonContent, 'domain-scores.json', 'application/json');
            }
        });
    </script>
</body>
</html>""")
    
    print(f"Templates created successfully in: {templates_dir}")

if __name__ == "__main__":
    create_templates()
    print("Dashboard ready! Starting server...")
    app.run(debug=True)