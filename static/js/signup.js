const passwordInput = document.getElementById('password');
const confirmPasswordInput = document.getElementById('confirmPassword');
const passwordRequirements = document.getElementById('passwordRequirements');
const submitBtn = document.getElementById('submitBtn');
const passwordMatch = document.getElementById('passwordMatch');

// Password requirements elements
const lengthReq = document.getElementById('length');
const uppercaseReq = document.getElementById('uppercase');
const lowercaseReq = document.getElementById('lowercase');
const numberReq = document.getElementById('number');
const specialReq = document.getElementById('special');
const strengthText = document.getElementById('strengthText');
const strengthBar = document.getElementById('strengthBar');

// Flash message close function
function closeFlashMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.style.animation = 'slideUp 0.3s ease-out';
        setTimeout(() => {
            message.remove();
        }, 300);
    }
}

// Auto-hide success messages after 8 seconds
setTimeout(() => {
    const flashMessages = document.querySelectorAll('.flash-message.success');
    flashMessages.forEach(message => {
        closeFlashMessage(message.id);
    });
}, 8000);

passwordInput.addEventListener('focus', () => {
    passwordRequirements.style.display = 'block';
    passwordRequirements.classList.add('active');
});

passwordInput.addEventListener('blur', () => {
    if (passwordInput.value === '') {
        passwordRequirements.style.display = 'none';
        passwordRequirements.classList.remove('active');
    }
});

passwordInput.addEventListener('input', checkPassword);
confirmPasswordInput.addEventListener('input', checkPasswordMatch);

function checkPassword() {
    const password = passwordInput.value;
    let validRequirements = 0;
    
    // Check length
    if (password.length >= 8) {
        lengthReq.classList.add('valid');
        lengthReq.classList.remove('invalid');
        validRequirements++;
    } else {
        lengthReq.classList.add('invalid');
        lengthReq.classList.remove('valid');
    }
    
    // Check uppercase
    if (/[A-Z]/.test(password)) {
        uppercaseReq.classList.add('valid');
        uppercaseReq.classList.remove('invalid');
        validRequirements++;
    } else {
        uppercaseReq.classList.add('invalid');
        uppercaseReq.classList.remove('valid');
    }
    
    // Check lowercase
    if (/[a-z]/.test(password)) {
        lowercaseReq.classList.add('valid');
        lowercaseReq.classList.remove('invalid');
        validRequirements++;
    } else {
        lowercaseReq.classList.add('invalid');
        lowercaseReq.classList.remove('valid');
    }
    
    // Check number
    if (/\d/.test(password)) {
        numberReq.classList.add('valid');
        numberReq.classList.remove('invalid');
        validRequirements++;
    } else {
        numberReq.classList.add('invalid');
        numberReq.classList.remove('valid');
    }
    
    // Check special character
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        specialReq.classList.add('valid');
        specialReq.classList.remove('invalid');
        validRequirements++;
    } else {
        specialReq.classList.add('invalid');
        specialReq.classList.remove('valid');
    }
    
    // Update strength bar and badge
    strengthBar.className = 'strength-fill';
    strengthText.className = 'badge';
    
    if (validRequirements <= 1) {
        strengthBar.classList.add('strength-weak');
        strengthText.classList.add('bg-danger');
        strengthText.textContent = 'Weak';
    } else if (validRequirements <= 2) {
        strengthBar.classList.add('strength-fair');
        strengthText.classList.add('bg-warning');
        strengthText.textContent = 'Fair';
    } else if (validRequirements <= 3) {
        strengthBar.classList.add('strength-good');
        strengthText.classList.add('bg-info');
        strengthText.textContent = 'Good';
    } else if (validRequirements >= 4) {
        strengthBar.classList.add('strength-strong');
        strengthText.classList.add('bg-success');
        strengthText.textContent = 'Strong';
    }
    
    checkFormValid();
}

function checkPasswordMatch() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    
    if (confirmPassword === '') {
        passwordMatch.textContent = '';
        passwordMatch.className = 'password-match';
    } else if (password === confirmPassword) {
        passwordMatch.textContent = '✓ Passwords match perfectly';
        passwordMatch.className = 'password-match valid';
    } else {
        passwordMatch.textContent = '✗ Passwords do not match';
        passwordMatch.className = 'password-match invalid';
    }
    
    checkFormValid();
}

function checkFormValid() {
    const userType = document.getElementById('userType').value;
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    const email = document.getElementById('email').value;
    const fullName = document.getElementById('fullName').value;
    
    // Check if password meets all requirements
    const hasLength = password.length >= 8;
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasNumber = /\d/.test(password);
    const hasSpecial = /[!@#$%^&*(),.?":{}|<>]/.test(password);
    
    const passwordValid = hasLength && hasUpper && hasLower && hasNumber && hasSpecial;
    const passwordsMatch = password === confirmPassword && confirmPassword !== '';
    const emailValid = email !== '' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    const nameValid = fullName.trim().length >= 2;
    const userTypeValid = userType !== '';
    
    if (passwordValid && passwordsMatch && emailValid && nameValid && userTypeValid) {
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
    } else {
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.6';
    }
}

// Add validation for other fields
document.getElementById('userType').addEventListener('change', checkFormValid);
document.getElementById('email').addEventListener('input', checkFormValid);
document.getElementById('fullName').addEventListener('input', checkFormValid);

// Form submission validation
document.getElementById('signupForm').addEventListener('submit', function(e) {
    const userType = document.getElementById('userType').value;
    const fullName = document.getElementById('fullName').value.trim();
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (!userType) {
        e.preventDefault();
        alert('Please select a user type (Candidate or Company).');
        return;
    }
    
    if (fullName.length < 2) {
        e.preventDefault();
        alert('Full name must be at least 2 characters long.');
        return;
    }
    
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        e.preventDefault();
        alert('Please enter a valid email address.');
        return;
    }
    
    if (password !== confirmPassword) {
        e.preventDefault();
        alert('Passwords do not match.');
        return;
    }
    
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Creating Account...';
});

// Add CSS for slideUp animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideUp {
        from {
            opacity: 1;
            transform: translateY(0);
        }
        to {
            opacity: 0;
            transform: translateY(-10px);
        }
    }
`;
document.head.appendChild(style);