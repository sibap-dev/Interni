document.addEventListener('DOMContentLoaded', () => {
    const uploadIcon = document.getElementById('uploadIcon');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const analysisResult = document.getElementById('analysisResult');
    const scoreValue = document.getElementById('scoreValue');
    const suggestionsList = document.getElementById('suggestionsList');
    const keywordsFound = document.getElementById('keywordsFound');
    const keywordsMissing = document.getElementById('keywordsMissing');

    if (!uploadIcon || !fileInput || !uploadBtn || !analysisResult) {
        return;
    }

    let selectedFile = null;

    function setAnalyzingState(isAnalyzing) {
        uploadBtn.disabled = isAnalyzing;
        uploadBtn.textContent = isAnalyzing ? 'Analyzing...' : 'Analyze CV';
    }

    function resetResult() {
        analysisResult.style.display = 'none';
        scoreValue.textContent = '0';
        suggestionsList.innerHTML = '';
        keywordsFound.innerHTML = '';
        keywordsMissing.innerHTML = '';
    }

    function showBadge(container, label, isMissing) {
        const tag = document.createElement('span');
        tag.textContent = label;
        tag.style.display = 'inline-block';
        tag.style.margin = '4px';
        tag.style.padding = '6px 10px';
        tag.style.borderRadius = '999px';
        tag.style.fontSize = '12px';
        tag.style.background = isMissing ? '#ffe6e6' : '#e6f4ea';
        tag.style.color = isMissing ? '#b42318' : '#137333';
        container.appendChild(tag);
    }

    function renderAnalysis(analysis) {
        const totalScore = Math.round(Number(analysis.total_score || 0));
        scoreValue.textContent = String(totalScore);

        suggestionsList.innerHTML = '';
        const recommendations = analysis.optimization_recommendations || [];
        if (recommendations.length === 0) {
            const li = document.createElement('li');
            li.textContent = 'No major issues found. Keep tailoring your CV to each job description.';
            suggestionsList.appendChild(li);
        } else {
            recommendations.forEach((item) => {
                const li = document.createElement('li');
                li.textContent = typeof item === 'string' ? item : (item.action || JSON.stringify(item));
                suggestionsList.appendChild(li);
            });
        }

        keywordsFound.innerHTML = '';
        keywordsMissing.innerHTML = '';

        const keywordAnalysis = analysis.keyword_analysis || {};
        const matchedCount = Number(keywordAnalysis.matched_keywords || 0);
        const totalKeywords = Number(keywordAnalysis.total_job_keywords || 0);
        const matchPercentage = Number(keywordAnalysis.match_percentage || 0);
        const missing = Array.isArray(keywordAnalysis.missing_keywords)
            ? keywordAnalysis.missing_keywords
            : (Array.isArray(keywordAnalysis.top_missing) ? keywordAnalysis.top_missing : []);

        keywordsFound.textContent = totalKeywords > 0
            ? `Matched ${matchedCount} of ${totalKeywords} job keywords (${matchPercentage}%).`
            : 'Keyword match metrics are available after adding a job description.';

        if (missing.length === 0) {
            keywordsMissing.textContent = 'No major missing keywords detected.';
        } else {
            missing.slice(0, 20).forEach((word) => showBadge(keywordsMissing, String(word), true));
        }

        analysisResult.style.display = 'block';
        analysisResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function analyzeSelectedFile() {
        if (!selectedFile) {
            alert('Please select your CV first.');
            return;
        }

        const allowedTypes = ['pdf', 'doc', 'docx', 'txt'];
        const ext = selectedFile.name.split('.').pop().toLowerCase();
        if (!allowedTypes.includes(ext)) {
            alert('Please upload a PDF, DOC, DOCX, or TXT file.');
            return;
        }

        setAnalyzingState(true);
        try {
            const formData = new FormData();
            formData.append('cv_file', selectedFile);
            formData.append('job_description', '');

            const response = await fetch('/analyze-cv', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Failed to analyze CV.');
            }

            renderAnalysis(data.analysis || {});
        } catch (error) {
            alert(error.message || 'Failed to analyze CV. Please try again.');
        } finally {
            setAnalyzingState(false);
        }
    }

    uploadIcon.addEventListener('click', () => fileInput.click());

    uploadBtn.addEventListener('click', () => {
        if (!selectedFile) {
            fileInput.click();
            return;
        }
        analyzeSelectedFile();
    });

    fileInput.addEventListener('change', (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) {
            return;
        }
        selectedFile = file;
        uploadBtn.textContent = `Analyze: ${file.name}`;
        resetResult();
    });

    uploadIcon.addEventListener('dragover', (event) => {
        event.preventDefault();
        uploadIcon.style.backgroundColor = '#eaf3ff';
    });

    uploadIcon.addEventListener('dragleave', () => {
        uploadIcon.style.backgroundColor = '';
    });

    uploadIcon.addEventListener('drop', (event) => {
        event.preventDefault();
        uploadIcon.style.backgroundColor = '';
        const file = event.dataTransfer.files && event.dataTransfer.files[0];
        if (!file) {
            return;
        }
        selectedFile = file;
        uploadBtn.textContent = `Analyze: ${file.name}`;
        resetResult();
    });
});