// Password visibility toggle function
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('password');
    const toggleIcon = document.getElementById('passwordToggleIcon');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        toggleIcon.className = 'fas fa-eye';
    }
}

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

// Auto-hide success messages after 5 seconds
setTimeout(() => {
    const flashMessages = document.querySelectorAll('.flash-message.success');
    flashMessages.forEach(message => {
        closeFlashMessage(message.id);
    });
}, 5000);

// Form submission handling
document.getElementById('loginForm').addEventListener('submit', function(e) {
    const loginBtn = document.getElementById('loginBtn');
    const userType = document.getElementById('userType').value;
    const email = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    // Basic validation
    if (!userType) {
        e.preventDefault();
        alert('Please select a user type (Candidate or Company).');
        return;
    }
    
    if (!email || !password) {
        e.preventDefault();
        alert('Please enter both email and password.');
        return;
    }
    
    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        e.preventDefault();
        alert('Please enter a valid email address.');
        return;
    }
    
    // Show loading state
    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Signing In...';
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

// Focus management
document.addEventListener('DOMContentLoaded', function() {
    const emailInput = document.getElementById('username');
    if (emailInput && !emailInput.value) {
        emailInput.focus();
    }
});