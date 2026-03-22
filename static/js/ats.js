document.addEventListener('DOMContentLoaded', function () {
    const uploadIcon = document.getElementById('uploadIcon');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const checkBtn = document.getElementById('checkBtn');
    const jobRole = document.getElementById('jobRole');
    const jobDescription = document.getElementById('jobDescription');

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

    function setButtonLoading(isLoading) {
        if (isLoading) {
            checkBtn.disabled = true;
            checkBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12,4V2A10,10 0 0,0 2,12H4A8,8 0 0,1 12,4Z" /></svg> Analyzing...';
        } else {
            checkBtn.disabled = false;
            checkBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z" /></svg> Check ATS Score';
        }
    }

    function addSuggestion(list, text, priority) {
        const li = document.createElement('li');
        li.className = 'suggestion-item';

        const icon = document.createElement('svg');
        icon.className = 'suggestion-icon';
        icon.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        icon.setAttribute('viewBox', '0 0 24 24');
        icon.innerHTML = '<path d="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M11,16.5L18,9.5L16.59,8.09L11,13.67L7.91,10.59L6.5,12L11,16.5Z" />';

        const span = document.createElement('span');
        span.textContent = text;
        span.className = `priority-${priority}`;

        li.appendChild(icon);
        li.appendChild(span);
        list.appendChild(li);
    }

    function clearSuggestionLists() {
        keywordSuggestions.innerHTML = '';
        contentSuggestions.innerHTML = '';
        formatSuggestions.innerHTML = '';
    }

    function renderSuggestions(analysis) {
        clearSuggestionLists();
        const optimization = Array.isArray(analysis.optimization_recommendations)
            ? analysis.optimization_recommendations
            : [];
        const criticalIssues = Array.isArray(analysis.critical_issues) ? analysis.critical_issues : [];
        const missingElements = Array.isArray(analysis.missing_elements) ? analysis.missing_elements : [];
        const guide = analysis.cv_improvement_guide || {};
        const includeItems = Array.isArray(guide.include) ? guide.include : [];
        const avoidItems = Array.isArray(guide.avoid) ? guide.avoid : [];

        optimization.forEach((item) => {
            const category = String(item.category || '').toLowerCase();
            const action = item.action || 'Improve this area based on ATS feedback.';
            const priority = String(item.priority || 'medium').toLowerCase();

            if (category.includes('keyword')) {
                addSuggestion(keywordSuggestions, action, priority);
            } else if (category.includes('format') || category.includes('structure')) {
                addSuggestion(formatSuggestions, action, priority);
            } else {
                addSuggestion(contentSuggestions, action, priority);
            }
        });

        criticalIssues.forEach((issue) => {
            addSuggestion(contentSuggestions, issue, 'high');
        });

        if (missingElements.length) {
            addSuggestion(keywordSuggestions, `Missing role-relevant terms: ${missingElements.join(', ')}`, 'medium');
        }

        includeItems.forEach((item) => {
            addSuggestion(contentSuggestions, `Include: ${item}`, 'high');
        });

        avoidItems.forEach((item) => {
            addSuggestion(formatSuggestions, `Avoid: ${item}`, 'medium');
        });

        if (!keywordSuggestions.children.length) {
            addSuggestion(keywordSuggestions, 'Keyword alignment is good for the selected role.', 'low');
        }
        if (!contentSuggestions.children.length) {
            addSuggestion(contentSuggestions, 'Content quality is acceptable. Add measurable achievements to improve further.', 'low');
        }
        if (!formatSuggestions.children.length) {
            addSuggestion(formatSuggestions, 'Formatting is mostly ATS-compatible for this role.', 'low');
        }
    }

    function renderAnalysis(analysis) {
        const score = Number(analysis.total_score || 0);
        const breakdown = analysis.detailed_breakdown || {};

        scoreValue.textContent = score.toFixed(1);
        scoreFill.style.width = `${Math.max(0, Math.min(100, score))}%`;

        keywordScore.textContent = `${Math.round(Number(breakdown.keyword_relevance || 0))}%`;
        formatScore.textContent = `${Math.round(Number(breakdown.format_compatibility || 0))}%`;
        projectScore.textContent = `${Math.round(Number(breakdown.skills_alignment || 0))}%`;
        experienceScore.textContent = `${Math.round(Number(breakdown.experience_match || 0))}%`;

        feedback.textContent = analysis.status_message || 'ATS analysis completed.';
        if (score >= 85) {
            feedback.style.color = '#27ae60';
        } else if (score >= 70) {
            feedback.style.color = '#f39c12';
        } else {
            feedback.style.color = '#e74c3c';
        }

        renderSuggestions(analysis);
        resultSection.style.display = 'block';
        suggestionsSection.style.display = 'block';
        resultSection.scrollIntoView({ behavior: 'smooth' });
    }

    uploadIcon.addEventListener('click', function () {
        fileInput.click();
    });

    fileInput.addEventListener('change', function (e) {
        if (e.target.files.length > 0) {
            uploadedFile = e.target.files[0];
            fileName.textContent = uploadedFile.name;
            fileName.style.color = '#27ae60';
            resultSection.style.display = 'none';
            suggestionsSection.style.display = 'none';
        }
    });

    checkBtn.addEventListener('click', async function () {
        if (!uploadedFile) {
            alert('Please upload your CV first.');
            return;
        }

        const role = (jobRole && jobRole.value) ? jobRole.value : 'general_internship';
        const jd = (jobDescription && jobDescription.value) ? jobDescription.value.trim() : '';

        setButtonLoading(true);
        try {
            const formData = new FormData();
            formData.append('cv_file', uploadedFile);
            formData.append('job_role', role);
            formData.append('job_description', jd);

            const response = await fetch('/analyze-cv', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data.success) {
                const message = data.error || data.message || `ATS analysis failed (${response.status}).`;
                alert(message);
                return;
            }

            renderAnalysis(data.analysis || {});
        } catch (_error) {
            alert('Network error while analyzing CV. Please try again.');
        } finally {
            setButtonLoading(false);
        }
    });

    uploadIcon.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadIcon.style.backgroundColor = '#e3f2fd';
        uploadIcon.style.borderColor = '#2980b9';
    });

    uploadIcon.addEventListener('dragleave', function () {
        uploadIcon.style.backgroundColor = '#f8f9fa';
        uploadIcon.style.borderColor = '#3498db';
    });

    uploadIcon.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadIcon.style.backgroundColor = '#f8f9fa';
        uploadIcon.style.borderColor = '#3498db';

        if (e.dataTransfer.files.length > 0) {
            uploadedFile = e.dataTransfer.files[0];
            fileName.textContent = uploadedFile.name;
            fileName.style.color = '#27ae60';
            resultSection.style.display = 'none';
            suggestionsSection.style.display = 'none';
        }
    });
});