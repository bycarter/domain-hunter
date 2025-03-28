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
        minScore: 0,
        pricedOnly: false,
        priceType: '',
        maxPrice: 0
    };
    
    // Elements
    const domainsTable = document.getElementById('domains-table');
    const searchInput = document.getElementById('search');
    const tldFilter = document.getElementById('tld-filter');
    const minScoreSlider = document.getElementById('min-score');
    const minScoreValue = document.getElementById('min-score-value');
    const priceTypeFilter = document.getElementById('price-type-filter');
    const maxPriceInput = document.getElementById('max-price');
    const applyFiltersBtn = document.getElementById('apply-filters');
    const domainDetails = document.getElementById('domain-details');
    const exportCsvBtn = document.getElementById('export-csv');
    const exportJsonBtn = document.getElementById('export-json');
    const pricedOnlyCheckbox = document.getElementById('priced-only');

    // Check if all required elements exist
    if (!domainsTable) {
        console.error("Error: Could not find domains-table element");
        return;
    }
    
    // Fetch initial data
    fetchDomains();
    fetchStats();
    
    // Debug - check if API endpoints are accessible
    console.log("Checking API endpoints...");
    fetch('/api/debug')
        .then(response => response.json())
        .then(data => {
            console.log("Debug API response:", data);
        })
        .catch(error => {
            console.error("Debug API error:", error);
        });
    
    // Event listeners
    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', fetchDomains);
    }
    
    if (minScoreSlider && minScoreValue) {
        minScoreSlider.addEventListener('input', function() {
            minScoreValue.textContent = this.value;
            filters.minScore = parseFloat(this.value);
        });
    }
    
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
            if (sortIcon) {
                sortIcon.classList.add(currentSort.direction);
            }
            
            fetchDomains();
        });
    });
    
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', exportCsv);
    }
    
    if (exportJsonBtn) {
        exportJsonBtn.addEventListener('click', exportJson);
    }
    if (pricedOnlyCheckbox) {
        pricedOnlyCheckbox.addEventListener('change', function() {
            filters.pricedOnly = this.checked;
            fetchDomains();
        });
    }
    
    // Functions
    function fetchDomains() {
        console.log("Fetching domains...");
        filters.search = searchInput ? searchInput.value.trim() : '';
        filters.tld = tldFilter ? tldFilter.value : '';
        filters.minScore = minScoreSlider ? parseFloat(minScoreSlider.value) : 0;
        filters.priceType = priceTypeFilter ? priceTypeFilter.value : '';
        filters.maxPrice = maxPriceInput ? (parseFloat(maxPriceInput.value) || 0) : 0;
        filters.pricedOnly = pricedOnlyCheckbox ? pricedOnlyCheckbox.checked : false;
        
        const params = new URLSearchParams({
            sort_by: currentSort.column,
            sort_dir: currentSort.direction,
            min_score: filters.minScore,
            tld: filters.tld,
            search: filters.search,
            price_type: filters.priceType,
            max_price: filters.maxPrice,
            priced_only: filters.pricedOnly ? '1' : '0'
        });
        
        fetch(`/api/domains?${params}`)
            .then(response => {
                console.log("API Response status:", response.status);
                return response.json();
            })
            .then(data => {
                console.log("Domains API data:", data);
                if (data.error) {
                    console.error('API Error:', data.error, data.message);
                    domainsTable.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error: ${data.message}</td></tr>`;
                    return;
                }
                
                domainsData = data;
                renderTable(data);
            })
            .catch(error => {
                console.error('Error fetching domains:', error);
                domainsTable.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Error loading data. Please try again.</td></tr>`;
            });
    }
    
    function fetchStats() {
        console.log("Fetching stats...");
        fetch('/api/stats')
            .then(response => {
                console.log("Stats API Response status:", response.status);
                return response.json();
            })
            .then(data => {
                console.log("Stats API data:", data);
                const totalDomainsElement = document.getElementById('total-domains');
                const avgScoreElement = document.getElementById('avg-score');
                const pricedDomainsElement = document.getElementById('priced-domains');
                
                if (totalDomainsElement) {
                    totalDomainsElement.textContent = data.total;
                }
                
                if (avgScoreElement) {
                    avgScoreElement.textContent = data.averages.avg_average_score 
                        ? parseFloat(data.averages.avg_average_score).toFixed(1)
                        : '-';
                }
                
                // Count priced domains
                let pricedDomains = 0;
                if (data.price_stats) {
                    data.price_stats.forEach(stat => {
                        if (stat.price_type !== 'Error') {
                            pricedDomains += stat.count;
                        }
                    });
                }
                
                if (pricedDomainsElement) {
                    pricedDomainsElement.textContent = pricedDomains;
                }
                
                // Populate TLD filter
                if (tldFilter) {
                    tldFilter.innerHTML = '<option value="">All TLDs</option>';
                    data.tlds.forEach(tld => {
                        const option = document.createElement('option');
                        option.value = tld.tld;
                        option.textContent = `.${tld.tld} (${tld.count})`;
                        tldFilter.appendChild(option);
                    });
                }
                
                // Render TLD distribution
                const tldContainer = document.getElementById('tld-container');
                if (tldContainer) {
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
                }
                
                // Render pricing stats
                const pricingContainer = document.getElementById('pricing-container');
                if (pricingContainer) {
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
                }
            })
            .catch(error => {
                console.error('Error fetching stats:', error);
            });
    }
    
    function renderTable(data) {
        if (!data || data.length === 0) {
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
        
        const detailDomainElement = document.getElementById('detail-domain');
        const detailMemorabilityElement = document.getElementById('detail-memorability');
        const detailPronunciationElement = document.getElementById('detail-pronunciation');
        const detailVisualAppealElement = document.getElementById('detail-visual_appeal');
        const detailBrandabilityElement = document.getElementById('detail-brandability');
        const detailPriceElement = document.getElementById('detail-price');
        const detailPriceTypeElement = document.getElementById('detail-price-type');
        const priceDetails = document.getElementById('price-details');
        
        if (detailDomainElement) {
            detailDomainElement.textContent = domain.domain;
        }
        
        if (detailMemorabilityElement) {
            detailMemorabilityElement.textContent = domain.memorability ? parseFloat(domain.memorability).toFixed(1) : '-';
        }
        
        if (detailPronunciationElement) {
            detailPronunciationElement.textContent = domain.pronunciation ? parseFloat(domain.pronunciation).toFixed(1) : '-';
        }
        
        if (detailVisualAppealElement) {
            detailVisualAppealElement.textContent = domain.visual_appeal ? parseFloat(domain.visual_appeal).toFixed(1) : '-';
        }
        
        if (detailBrandabilityElement) {
            detailBrandabilityElement.textContent = domain.brandability ? parseFloat(domain.brandability).toFixed(1) : '-';
        }
        
        // Set price details
        if (detailPriceElement) {
            detailPriceElement.textContent = domain.price ? `$${parseFloat(domain.price).toFixed(2)}` : '-';
        }
        
        if (detailPriceTypeElement) {
            detailPriceTypeElement.textContent = domain.price_type || '-';
        }
        
        // Show/hide price details
        if (priceDetails) {
            priceDetails.style.display = domain.price_type ? 'block' : 'none';
        }
        
        // Highlight selected row
        document.querySelectorAll('.domain-item').forEach(row => {
            row.classList.remove('table-active');
        });
        
        const selectedRow = document.querySelector(`.domain-item[data-index="${index}"]`);
        if (selectedRow) {
            selectedRow.classList.add('table-active');
        }
        
        if (domainDetails) {
            domainDetails.classList.remove('d-none');
        }
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