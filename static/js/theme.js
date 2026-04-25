// 🎨 ENHANCED THEME MANAGER + ANIMATIONS (REPLACE YOUR theme.js)
class EasyPDFApp {
    constructor() {
        this.init();
    }

    init() {
        this.loadTheme();
        this.bindEvents();
        this.observeAnimations();
    }

    // 🌙 THEME SYSTEM (YOUR CODE ENHANCED)
    loadTheme() {
        const savedTheme = localStorage.getItem('easypdf-theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateToggle(savedTheme);
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('easypdf-theme', newTheme);
        this.updateToggle(newTheme);
    }

    updateToggle(theme) {
        const toggle = document.querySelector('.theme-toggle');
        if (toggle) {
            toggle.innerHTML = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
        }
    }

    // ⚡ EVENTS
    bindEvents() {
        document.addEventListener('click', (e) => {
            // Theme toggle
            if (e.target.classList.contains('theme-toggle')) {
                this.toggleTheme();
            }
            
            // Upload animations
            if (e.target.closest('.upload-box')) {
                this.animateUpload(e.target.closest('.upload-box'));
            }
        });

        // File inputs
        document.querySelectorAll('input[type="file"]').forEach(input => {
            input.addEventListener('change', (e) => this.handleFileSelect(e));
        });
    }

    animateUpload(box) {
        box.innerHTML = `
            <div style="padding: 3rem 2rem; text-align: center;">
                <div class="loader" style="width: 60px; height: 60px; margin: 0 auto 1.5rem; border-color: var(--accent);"></div>
                <div style="font-size: 1.3rem; font-weight: 600; color: var(--accent);">Uploading...</div>
            </div>
        `;
        setTimeout(() => box.closest('form').submit(), 1000);
    }

    handleFileSelect(e) {
        const input = e.target;
        const box = input.parentElement;
        const files = Array.from(input.files);
        
        if (files.length) {
            box.querySelector('.upload-subtext').textContent = `${files.length} file(s) selected`;
        }
    }

    // 📊 PROGRESS ANIMATIONS
    static animateProgress(percent, selector = '.progress-fill') {
        const circle = document.querySelector(selector);
        if (!circle) return;
        
        const radius = 65;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference - (percent / 100) * circumference;
        
        circle.style.strokeDasharray = `${circumference} ${circumference}`;
        circle.style.strokeDashoffset = offset;
    }

    static showResult(savedPercent) {
        const loading = document.getElementById('loading');
        const result = document.getElementById('result');
        
        if (loading && result) {
            loading.style.transition = 'opacity 0.8s ease';
            loading.style.opacity = '0';
            
            setTimeout(() => {
                loading.style.display = 'none';
                result.style.display = 'block';
                result.style.opacity = '1';
                
                setTimeout(() => {
                    this.animateProgress(savedPercent);
                }, 200);
            }, 800);
        }
    }

    // 🎬 SCROLL ANIMATIONS
    observeAnimations() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animate');
                }
            });
        }, { threshold: 0.1 });

        document.querySelectorAll('.fade-in, .card').forEach(el => {
            observer.observe(el);
        });
    }
}

// 🚀 AUTO INIT
document.addEventListener('DOMContentLoaded', () => {
    new EasyPDFApp();

    // Auto-run result page animation
    const savedData = document.getElementById('saved-data');
    if (savedData) {
        const data = JSON.parse(savedData.textContent);
        setTimeout(() => EasyPDFApp.showResult(data.percent), 1200);
    }
});