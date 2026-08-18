const API_BASE_URL = "http://localhost:8000/api";

function toggleForms() {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    
    if (loginForm.style.display === 'none') {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    } else {
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    }
    
    // Clear errors
    document.getElementById('login-error').style.display = 'none';
    document.getElementById('reg-error').style.display = 'none';
}

async function handleRegister() {
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const errorEl = document.getElementById('reg-error');
    const btn = document.getElementById('reg-btn');
    
    if (!email || !password) {
        showError(errorEl, "Please fill in all fields.");
        return;
    }
    
    btn.disabled = true;
    btn.innerText = "Creating...";
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert("Account created successfully! Please sign in.");
            toggleForms();
        } else {
            showError(errorEl, data.detail || "Registration failed");
        }
    } catch (e) {
        showError(errorEl, "Connection error. Please try again.");
    } finally {
        btn.disabled = false;
        btn.innerText = "Create Account";
    }
}

async function handleLogin() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    const btn = document.getElementById('login-btn');
    
    if (!email || !password) {
        showError(errorEl, "Please fill in all fields.");
        return;
    }
    
    btn.disabled = true;
    btn.innerText = "Signing In...";
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('adminToken', data.access_token);
            window.location.href = "/";
        } else {
            showError(errorEl, data.detail || "Invalid credentials");
        }
    } catch (e) {
        showError(errorEl, "Connection error. Please try again.");
    } finally {
        btn.disabled = false;
        btn.innerText = "Sign In";
    }
}

function showError(element, message) {
    element.innerText = message;
    element.style.display = 'block';
}

// Redirect to dashboard if already logged in
document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('adminToken')) {
        window.location.href = "/";
    }
});
