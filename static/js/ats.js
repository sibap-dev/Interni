        document.addEventListener('DOMContentLoaded', function() {
            const uploadIcon = document.getElementById('uploadIcon');
            const fileInput = document.getElementById('fileInput');
            const fileName = document.getElementById('fileName');
            const checkBtn = document.getElementById('checkBtn');
            const resultSection = document.getElementById('resultSection');
            const scoreValue = document.getElementById('scoreValue');
            const scoreFill = document.getElementById('scoreFill');
            const feedback = document.getElementById('feedback');
            const keywordScore = document.getElementById('keywordScore');
            const formatScore = document.getElementById('formatScore');
            const projectScore = document.getElementById('projectScore');
            const experienceScore = document.getElementById('experienceScore');
            const suggestionsSection = document.getElementById('suggestionsSection');
            const keywordSuggestions = document.getElementById('keywordSuggestions');
            const contentSuggestions = document.getElementById('contentSuggestions');
            const formatSuggestions = document.getElementById('formatSuggestions');
            
            let uploadedFile = null;
            
            // Handle file upload
            uploadIcon.addEventListener('click', function() {
                fileInput.click();
            });
            
            fileInput.addEventListener('change', function(e) {
                if (e.target.files.length > 0) {
                    uploadedFile = e.target.files[0];
                    fileName.textContent = uploadedFile.name;
                    fileName.style.color = '#27ae60';
                    
                    // Reset results if a new file is uploaded
                    resultSection.style.display = 'none';
                    suggestionsSection.style.display = 'none';
                }
            });
            
            // Handle ATS score check
            checkBtn.addEventListener('click', function() {
                if (!uploadedFile) {
                    alert('Please upload your CV first.');
                    return;
                }
                
                // Show loading state
                checkBtn.disabled = true;
                checkBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12,4V2A10,10 0 0,0 2,12H4A8,8 0 0,1 12,4Z" /></svg> Analyzing...';
                
                // Simulate analysis process
                setTimeout(function() {
                    // Generate random scores for demonstration
                    const keywordMatch = Math.floor(Math.random() * 40) + 60; // 60-100
                    const formatting = Math.floor(Math.random() * 30) + 70; // 70-100
                    const projects = Math.floor(Math.random() * 50) + 50; // 50-100
                    const experience = Math.floor(Math.random() * 60) + 40; // 40-100
                    
                    // Calculate overall score (weighted average)
                    const overallScore = Math.round(
                        keywordMatch * 0.4 + 
                        formatting * 0.2 + 
                        projects * 0.3 + 
                        experience * 0.1
                    );
                    
                    // Update UI with scores
                    scoreValue.textContent = overallScore;
                    scoreFill.style.width = `${overallScore}%`;
                    keywordScore.textContent = `${keywordMatch}%`;
                    formatScore.textContent = `${formatting}%`;
                    projectScore.textContent = `${projects}%`;
                    experienceScore.textContent = `${experience}%`;
                    
                    // Provide feedback based on score
                    if (overallScore >= 85) {
                        feedback.textContent = "Excellent! Your CV is well-optimized for ATS.";
                        feedback.style.color = "#27ae60";
                    } else if (overallScore >= 70) {
                        feedback.textContent = "Good! Your CV has potential but could be improved.";
                        feedback.style.color = "#f39c12";
                    } else {
                        feedback.textContent = "Needs improvement. Consider optimizing your CV.";
                        feedback.style.color = "#e74c3c";
                    }
                    
                    // Generate suggestions based on scores
                    generateSuggestions(keywordMatch, formatting, projects, experience, overallScore);
                    
                    // Show results
                    resultSection.style.display = 'block';
                    suggestionsSection.style.display = 'block';
                    
                    // Reset button
                    checkBtn.disabled = false;
                    checkBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z" /></svg> Check ATS Score';
                    
                    // Scroll to results
                    resultSection.scrollIntoView({ behavior: 'smooth' });
                }, 2000);
            });
            
            // Generate personalized suggestions
            function generateSuggestions(keywordMatch, formatting, projects, experience, overallScore) {
                // Clear previous suggestions
                keywordSuggestions.innerHTML = '';
                contentSuggestions.innerHTML = '';
                formatSuggestions.innerHTML = '';
                
                // Keyword suggestions
                if (keywordMatch < 80) {
                    addSuggestion(keywordSuggestions, "Add more industry-specific keywords from the job description", "high");
                    addSuggestion(keywordSuggestions, "Include both acronyms and full forms of technical terms (e.g., 'API' and 'Application Programming Interface')", "medium");
                }
                
                if (keywordMatch < 70) {
                    addSuggestion(keywordSuggestions, "Create a 'Skills' section with relevant technical and soft skills", "high");
                    addSuggestion(keywordSuggestions, "Incorporate action verbs like 'developed', 'managed', 'optimized'", "medium");
                }
                
                if (keywordMatch >= 80) {
                    addSuggestion(keywordSuggestions, "Your keyword optimization is good. Maintain this level for future applications", "low");
                }
                
                // Content suggestions
                if (projects < 70) {
                    addSuggestion(contentSuggestions, "Add 2-3 relevant projects with detailed descriptions", "high");
                    addSuggestion(contentSuggestions, "Include technologies used and your specific contributions", "medium");
                }
                
                if (experience < 60) {
                    addSuggestion(contentSuggestions, "Highlight transferable skills from non-related experiences", "medium");
                    addSuggestion(contentSuggestions, "Add volunteer work or extracurricular activities that demonstrate relevant skills", "medium");
                }
                
                if (overallScore < 70) {
                    addSuggestion(contentSuggestions, "Add a professional summary at the top of your CV", "medium");
                    addSuggestion(contentSuggestions, "Quantify achievements with numbers (e.g., 'Improved efficiency by 25%')", "high");
                }
                
                // Formatting suggestions
                if (formatting < 80) {
                    addSuggestion(formatSuggestions, "Use clear section headings (Education, Experience, Skills, Projects)", "high");
                    addSuggestion(formatSuggestions, "Ensure consistent formatting (dates, bullet points, fonts)", "medium");
                }
                
                if (formatting < 70) {
                    addSuggestion(formatSuggestions, "Keep your CV to 1-2 pages maximum", "high");
                    addSuggestion(formatSuggestions, "Use a clean, professional font like Arial or Calibri (10-12pt)", "medium");
                }
                
                if (formatting >= 80) {
                    addSuggestion(formatSuggestions, "Your CV formatting is good. Consider adding subtle design elements to stand out", "low");
                }
                
                // General suggestions based on overall score
                if (overallScore < 60) {
                    addSuggestion(contentSuggestions, "Consider using a CV template designed for ATS compatibility", "high");
                    addSuggestion(contentSuggestions, "Tailor your CV specifically for each job application", "high");
                }
            }
            
            // Helper function to add suggestions to the list
            function addSuggestion(list, text, priority) {
                const li = document.createElement('li');
                li.className = 'suggestion-item';
                
                const icon = document.createElement('svg');
                icon.className = 'suggestion-icon';
                icon.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
                icon.setAttribute('viewBox', '0 0 24 24');
                icon.innerHTML = '<path d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,12 0 0,1 12,2M11,16.5L18,9.5L16.59,8.09L11,13.67L7.91,10.59L6.5,12L11,16.5Z" />';
                
                const span = document.createElement('span');
                span.textContent = text;
                span.className = `priority-${priority}`;
                
                li.appendChild(icon);
                li.appendChild(span);
                list.appendChild(li);
            }
            
            // Add drag and drop functionality
            uploadIcon.addEventListener('dragover', function(e) {
                e.preventDefault();
                uploadIcon.style.backgroundColor = '#e3f2fd';
                uploadIcon.style.borderColor = '#2980b9';
            });
            
            uploadIcon.addEventListener('dragleave', function() {
                uploadIcon.style.backgroundColor = '#f8f9fa';
                uploadIcon.style.borderColor = '#3498db';
            });
            
            uploadIcon.addEventListener('drop', function(e) {
                e.preventDefault();
                uploadIcon.style.backgroundColor = '#f8f9fa';
                uploadIcon.style.borderColor = '#3498db';
                
                if (e.dataTransfer.files.length > 0) {
                    uploadedFile = e.dataTransfer.files[0];
                    fileName.textContent = uploadedFile.name;
                    fileName.style.color = '#27ae60';
                    
                    // Reset results if a new file is uploaded
                    resultSection.style.display = 'none';
                    suggestionsSection.style.display = 'none';
                }
            });
        });