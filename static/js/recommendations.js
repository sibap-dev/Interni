        document.addEventListener('DOMContentLoaded', function() {
            const tabButtons = document.querySelectorAll('.tab-btn');
            const cards = document.querySelectorAll('.recommendation-card');
            const emptyState = document.getElementById('emptyState');
            const refreshBtn = document.getElementById('refreshRecommendations');
            const loadingSpinner = document.getElementById('loadingSpinner');
            const recommendationsContainer = document.getElementById('recommendationsContainer');

            // 🔧 NEW: TAB FILTERING FUNCTIONALITY
            tabButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const filter = this.dataset.filter;
                    
                    // Update active tab
                    tabButtons.forEach(btn => btn.classList.remove('active'));
                    this.classList.add('active');
                    
                    // Filter cards
                    filterRecommendations(filter);
                });
            });

            function filterRecommendations(filter) {
                let visibleCount = 0;
                
                cards.forEach(card => {
                    const cardType = card.dataset.type;
                    
                    if (filter === 'all' || cardType === filter) {
                        card.style.display = 'block';
                        visibleCount++;
                    } else {
                        card.style.display = 'none';
                    }
                });

                // Show/hide empty state
                if (visibleCount === 0) {
                    recommendationsContainer.style.display = 'none';
                    emptyState.style.display = 'block';
                } else {
                    recommendationsContainer.style.display = 'grid';
                    emptyState.style.display = 'none';
                }
            }

            // 🔧 ENHANCED: REFRESH RECOMMENDATIONS WITH TAB UPDATES
            refreshBtn.addEventListener('click', function() {
                // Show loading state
                refreshBtn.disabled = true;
                refreshBtn.querySelector('span').textContent = 'Generating...';
                refreshBtn.querySelector('i').classList.add('fa-spin');
                loadingSpinner.style.display = 'block';
                recommendationsContainer.style.opacity = '0.5';

                // Make AJAX request for new recommendations
                fetch('/api/generate-ai-recommendations')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success && data.recommendations) {
                            // Clear existing recommendations
                            recommendationsContainer.innerHTML = '';

                            // Count recommendations by type
                            let govCount = 0;
                            let privateCount = 0;

                            // Add new recommendations
                            data.recommendations.forEach(rec => {
                                if (rec.type === 'government') govCount++;
                                if (rec.type === 'private-based') privateCount++;
                                
                                const cardHTML = createRecommendationCard(rec);
                                recommendationsContainer.innerHTML += cardHTML;
                            });

                            // Update tab counts
                            document.getElementById('allCount').textContent = data.recommendations.length;
                            document.getElementById('govCount').textContent = govCount;
                            document.getElementById('privateCount').textContent = privateCount;

                            // Re-apply current filter
                            const activeTab = document.querySelector('.tab-btn.active');
                            const currentFilter = activeTab.dataset.filter;
                            
                            // Update cards reference and filter
                            setTimeout(() => {
                                const newCards = document.querySelectorAll('.recommendation-card');
                                filterCards(newCards, currentFilter);
                            }, 100);

                            // Show success message
                            showFlashMessage('Fresh recommendations generated based on your profile!', 'success');
                        } else {
                            showFlashMessage('Error generating recommendations. Please try again.', 'error');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        showFlashMessage('Network error. Please check your connection and try again.', 'error');
                    })
                    .finally(() => {
                        // Reset button state
                        refreshBtn.disabled = false;
                        refreshBtn.querySelector('span').textContent = 'Generate New';
                        refreshBtn.querySelector('i').classList.remove('fa-spin');
                        loadingSpinner.style.display = 'none';
                        recommendationsContainer.style.opacity = '1';
                    });
            });

            function filterCards(cardElements, filter) {
                let visibleCount = 0;
                
                cardElements.forEach(card => {
                    const cardType = card.dataset.type;
                    
                    if (filter === 'all' || cardType === filter) {
                        card.style.display = 'block';
                        visibleCount++;
                    } else {
                        card.style.display = 'none';
                    }
                });

                // Show/hide empty state
                if (visibleCount === 0) {
                    recommendationsContainer.style.display = 'none';
                    emptyState.style.display = 'block';
                } else {
                    recommendationsContainer.style.display = 'grid';
                    emptyState.style.display = 'none';
                }
            }

            function createRecommendationCard(rec) {
                const skillsHTML = rec.skills ? rec.skills.map(skill => 
                    `<span class="skill-chip">${skill}</span>`
                ).join('') : '';

                const skillMatchScore = rec.skill_match_score || 75;
                const cardClass = rec.type === 'government' ? 'government-card' : 'private-card';

                return `
                    <div class="recommendation-card ${cardClass}" data-type="${rec.type}">
                        <div class="card-header">
                            <div class="company-info">
                                <h4>${rec.company}</h4>
                                <div class="job-title">${rec.title}</div>
                            </div>
                            <span class="type-badge ${rec.type}">
                                ${rec.type === 'government' ? 
                                    '<i class="fas fa-university"></i> Government' : 
                                    '<i class="fas fa-building"></i> Private-Based'}
                            </span>
                        </div>
                        <div class="card-content">
                            <div class="info-row">
                                <span class="info-label"><i class="fas fa-industry"></i> Sector:</span>
                                <span class="info-value">${rec.sector}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label"><i class="fas fa-clock"></i> Duration:</span>
                                <span class="info-value">${rec.duration}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label"><i class="fas fa-map-marker-alt"></i> Location:</span>
                                <span class="info-value">${rec.location}</span>
                            </div>
                            <div class="info-row">
                                <span class="info-label"><i class="fas fa-rupee-sign"></i> Stipend:</span>
                                <span class="info-value" style="color: var(--success-color); font-weight: 600;">
                                    ${rec.stipend}
                                </span>
                            </div>
                            <div class="description">${rec.description}</div>
                            ${rec.skills ? `
                                <div class="skills-match">
                                    <div class="skill-match-circle">
                                        <div class="circle-bg" style="--percentage: ${skillMatchScore}">
                                            <div class="circle-inner">
                                                <div class="match-percentage">${skillMatchScore}%</div>
                                                <div class="match-label">Match</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="skills-info">
                                        <div style="margin-bottom: 8px;">
                                            <strong><i class="fas fa-tools"></i> Required Skills:</strong>
                                        </div>
                                        <div class="required-skills">${skillsHTML}</div>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }

            function showFlashMessage(message, type) {
                const flashMessages = document.querySelector('.flash-messages') || createFlashContainer();
                const flashDiv = document.createElement('div');
                flashDiv.className = `flash-message flash-${type}`;
                flashDiv.innerHTML = `<i class="fas fa-info-circle"></i> ${message}`;
                
                flashMessages.appendChild(flashDiv);
                
                // Remove after 5 seconds
                setTimeout(() => {
                    flashDiv.remove();
                }, 5000);
            }

            function createFlashContainer() {
                const container = document.createElement('div');
                container.className = 'flash-messages';
                document.querySelector('.container').insertBefore(container, document.querySelector('header').nextSibling);
                return container;
            }
        });