        // PROFILE MANAGEMENT FUNCTIONS
        let isEditMode = false;
        let profileCompleted = window.profileCompleted || false;function toggleEditProfile() {
    const form = document.getElementById('registrationForm');
    const editBtn = document.getElementById('editProfileBtn');
    const submitBtn = document.querySelector('.submit-btn');
    const allInputs = form.querySelectorAll('input:not([type="radio"]):not([type="checkbox"]), select, textarea');
    const radioInputs = form.querySelectorAll('input[type="radio"], input[type="checkbox"]');
    const multiselects = form.querySelectorAll('.multiselect');
    const buttons = form.querySelectorAll('button:not(#editProfileBtn)');

    isEditMode = !isEditMode;

    if (isEditMode) {
        form.classList.remove('form-readonly');
        allInputs.forEach(input => input.disabled = false);
        radioInputs.forEach(input => input.disabled = false);
        buttons.forEach(btn => btn.disabled = false);
        multiselects.forEach(ms => {
            ms.style.pointerEvents = 'auto';
            ms.style.backgroundColor = '';
            ms.style.cursor = '';
            ms.style.borderColor = '';
        });

        editBtn.textContent = 'Cancel Edit';
        submitBtn.style.display = 'block';
        submitBtn.textContent = 'Update Profile';
    } else {
        form.classList.add('form-readonly');
        allInputs.forEach(input => input.disabled = true);
        radioInputs.forEach(input => input.disabled = true);
        buttons.forEach(btn => btn.disabled = true);
        multiselects.forEach(ms => {
            ms.style.pointerEvents = 'none';
            ms.style.backgroundColor = '#f8f9fa';
            ms.style.cursor = 'not-allowed';
            ms.style.borderColor = '#e9ecef';
        });

        editBtn.textContent = 'Edit Profile';
        submitBtn.style.display = 'none';
        submitBtn.textContent = 'Submit Registration';
    }
}

function showProfileActions() {
    const profileActions = document.getElementById('profileActions');
    const form = document.getElementById('registrationForm');
    const submitBtn = document.querySelector('.submit-btn');

    profileActions.classList.add('show');
    form.classList.add('form-readonly');
    
    const allInputs = form.querySelectorAll('input, select, textarea, button:not(#editProfileBtn)');
    allInputs.forEach(input => {
        if (input.type !== 'submit') {
            input.disabled = true;
        }
    });

    const multiselects = form.querySelectorAll('.multiselect');
    multiselects.forEach(ms => {
        ms.style.pointerEvents = 'none';
        ms.style.backgroundColor = '#f8f9fa';
        ms.style.cursor = 'not-allowed';
        ms.style.borderColor = '#e9ecef';
    });

    submitBtn.style.display = 'none';
    profileCompleted = true;
}

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('registrationForm');
    const generateOtpBtn = document.getElementById('generateOtp');
    const otpInput = document.getElementById('otp');
    const internshipYes = document.getElementById('internshipYes');
    const internshipNo = document.getElementById('internshipNo');
    const internshipCertificateGroup = document.getElementById('internshipCertificateGroup');
    const successMessage = document.getElementById('successMessage');
    
    // Skills and Languages dropdowns
    const skillsMultiselect = document.getElementById('skillsMultiselect');
    const skillsDropdown = document.getElementById('skillsDropdown');
    const skillsSelected = document.getElementById('skillsSelected');
    const skillsCheckboxes = skillsDropdown.querySelectorAll('input[type="checkbox"]');
    
    const languagesMultiselect = document.getElementById('languagesMultiselect');
    const languagesDropdown = document.getElementById('languagesDropdown');
    const languagesSelected = document.getElementById('languagesSelected');
    const languagesCheckboxes = languagesDropdown.querySelectorAll('input[type="checkbox"]');
    
    // Project Management
    const projectsContainer = document.getElementById('projectsContainer');
    const addProjectBtn = document.getElementById('addProject');
    
    // Achievements Management
    const achievementsContainer = document.getElementById('achievementsContainer');
    const addAchievementBtn = document.getElementById('addAchievement');
    
    // Certifications Management
    const certificationsContainer = document.getElementById('certificationsContainer');
    const addCertificationBtn = document.getElementById('addCertification');

    // 🔧 REMOVED: All area of interest auto-sync JavaScript
    // Career Objective and Area of Interest are now completely separate
    // - Career Objective (textarea) = Pure user input, no interference
    // - Area of Interest (dropdown) = Separate selection, no auto-filling
    
    // Initialize profile state
    if (profileCompleted) {
        showProfileActions();
        updateSelectedItems(skillsCheckboxes, skillsSelected, skillsMultiselect);
        updateSelectedItems(languagesCheckboxes, languagesSelected, languagesMultiselect);
    }
    
    // Skills dropdown functionality
    skillsMultiselect.addEventListener('click', function() {
        if (!profileCompleted || isEditMode) {
            skillsDropdown.classList.toggle('show');
            skillsMultiselect.classList.toggle('active');
            languagesDropdown.classList.remove('show');
            languagesMultiselect.classList.remove('active');
        }
    });
    
    // Languages dropdown functionality
    languagesMultiselect.addEventListener('click', function() {
        if (!profileCompleted || isEditMode) {
            languagesDropdown.classList.toggle('show');
            languagesMultiselect.classList.toggle('active');
            skillsDropdown.classList.remove('show');
            skillsMultiselect.classList.remove('active');
        }
    });
    
    // Achievement Remove Button Functionality
    achievementsContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-btn')) {
            const achievementItem = e.target.closest('.achievement-item');
            if (achievementItem && (!profileCompleted || isEditMode)) {
                achievementItem.remove();
            }
        }
    });

    // Certification Remove Button Functionality
    certificationsContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-btn')) {
            const certificationItem = e.target.closest('.certification-item');
            if (certificationItem && (!profileCompleted || isEditMode)) {
                certificationItem.remove();
            }
        }
    });

    // Update selected items display
    skillsCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedItems(skillsCheckboxes, skillsSelected, skillsMultiselect);
        });
    });
    
    languagesCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedItems(languagesCheckboxes, languagesSelected, languagesMultiselect);
        });
    });
    
    function updateSelectedItems(checkboxes, selectedContainer, multiselect) {
        selectedContainer.innerHTML = '';
        let selectedCount = 0;
        
        checkboxes.forEach(checkbox => {
            if (checkbox.checked) {
                selectedCount++;
                const item = document.createElement('div');
                item.className = 'selected-item';
                item.innerHTML = `${checkbox.parentElement.textContent.trim()} <span>×</span>`;
                
                item.querySelector('span').addEventListener('click', function(e) {
                    e.stopPropagation();
                    if (!profileCompleted || isEditMode) {
                        checkbox.checked = false;
                        updateSelectedItems(checkboxes, selectedContainer, multiselect);
                    }
                });
                
                selectedContainer.appendChild(item);
            }
        });
        
        if (selectedCount === 0) {
            multiselect.textContent = multiselect.id === 'skillsMultiselect' ? 'Select Skills' : 'Select Languages';
        } else {
            multiselect.textContent = `${selectedCount} selected`;
        }
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!skillsMultiselect.contains(e.target) && !skillsDropdown.contains(e.target)) {
            skillsDropdown.classList.remove('show');
            skillsMultiselect.classList.remove('active');
        }
        
        if (!languagesMultiselect.contains(e.target) && !languagesDropdown.contains(e.target)) {
            languagesDropdown.classList.remove('show');
            languagesMultiselect.classList.remove('active');
        }
    });
    
    // Project Management with Event Delegation
    projectsContainer.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-btn')) {
            const projectItem = e.target.closest('.project-item');
            if (confirm('Remove this project? (Projects are optional)')) {
                projectItem.remove();
            }
        }
    });
    
    addProjectBtn.addEventListener('click', function() {
        if (projectsContainer.children.length >= 5) {
            alert('Maximum 5 projects allowed');
            return;
        }
        
        const projectItem = document.createElement('div');
        projectItem.className = 'project-item';
        projectItem.innerHTML = `
            <div class="project-header">
                <input type="text" class="project-title" placeholder="Project Title (Optional)">
                <div class="project-links">
                    <input type="url" class="project-link-input" placeholder="Project Link (optional)">
                    <input type="url" class="github-link-input" placeholder="GitHub Link (optional)">
                </div>
                <button type="button" class="remove-btn">Remove</button>
            </div>
            <textarea class="project-description" placeholder="Project Description (technologies used, your role, outcomes) - Optional" rows="3"></textarea>
        `;
        
        projectsContainer.appendChild(projectItem);
    });
    
    // Add Achievement Functionality
    addAchievementBtn.addEventListener('click', function() {
        const achievementItem = document.createElement('div');
        achievementItem.className = 'achievement-item';
        achievementItem.innerHTML = `
            <div class="achievement-details">
                <input type="text" class="achievement-title" placeholder="Achievement Title">
                <textarea class="achievement-description" placeholder="Description (context, significance)" rows="2"></textarea>
            </div>
            <input type="text" class="achievement-year" placeholder="Year" maxlength="4">
            <button type="button" class="remove-btn">Remove</button>
        `;
        
        achievementsContainer.appendChild(achievementItem);
        
        achievementItem.querySelector('.remove-btn').addEventListener('click', function() {
            achievementItem.remove();
        });
    });
    
    // Add Certification Functionality
    addCertificationBtn.addEventListener('click', function() {
        const certificationItem = document.createElement('div');
        certificationItem.className = 'certification-item';
        certificationItem.innerHTML = `
            <div class="certification-details">
                <input type="text" class="certification-title" placeholder="Certification Name">
                <input type="text" class="certification-issuer" placeholder="Issuing Organization">
                <input type="text" class="certification-id" placeholder="Credential ID (optional)">
            </div>
            <input type="month" class="certification-date">
            <button type="button" class="remove-btn">Remove</button>
        `;
        
        certificationsContainer.appendChild(certificationItem);
        
        certificationItem.querySelector('.remove-btn').addEventListener('click', function() {
            certificationItem.remove();
        });
    });
    
    // OTP Generation
    generateOtpBtn.addEventListener('click', function() {
        const phoneInput = document.getElementById('phone');
        if (phoneInput.value.trim() === '') {
            alert('Please enter your phone number first');
            phoneInput.focus();
            return;
        }
        
        const otp = Math.floor(100000 + Math.random() * 900000);
        alert(`OTP for ${phoneInput.value} is: ${otp}\n\n(In a real application, this would be sent via SMS)`);
        otpInput.value = otp;
        
        generateOtpBtn.disabled = true;
        generateOtpBtn.textContent = 'Resend OTP in 60s';
        
        let countdown = 60;
        const countdownInterval = setInterval(() => {
            countdown--;
            generateOtpBtn.textContent = `Resend OTP in ${countdown}s`;
            
            if (countdown <= 0) {
                clearInterval(countdownInterval);
                generateOtpBtn.disabled = false;
                generateOtpBtn.textContent = 'Send OTP';
            }
        }, 1000);
    });
    
    // Show/hide internship certificate upload
    internshipYes?.addEventListener('change', function() {
        if (this.checked) {
            internshipCertificateGroup.classList.remove('hidden');
        }
    });
    
    internshipNo?.addEventListener('change', function() {
        if (this.checked) {
            internshipCertificateGroup.classList.add('hidden');
        }
    });
    
    // Form submission handling
    form.addEventListener('submit', function(e) {
        setTimeout(() => {
            successMessage.style.display = 'block';
            successMessage.scrollIntoView({ behavior: 'smooth' });
            
            showProfileActions();
            
            setTimeout(() => {
                successMessage.style.display = 'none';
            }, 5000);
        }, 100);
    });
    
    // Initialize dropdown displays on page load
    updateSelectedItems(skillsCheckboxes, skillsSelected, skillsMultiselect);
    updateSelectedItems(languagesCheckboxes, languagesSelected, languagesMultiselect);
});