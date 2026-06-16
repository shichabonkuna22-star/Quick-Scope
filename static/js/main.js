// QuickScope Main JavaScript – v2 with Intersection Observer
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    if (menu) { menu.classList.toggle('open'); }
}

document.addEventListener('DOMContentLoaded', function() {
    // Close mobile menu on link click
    const mobileMenu = document.getElementById('mobileMenu');
    if (mobileMenu) {
        mobileMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => { mobileMenu.classList.remove('open'); });
        });
    }

    // Auto-dismiss flash messages
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 300);
        }, 5000);
    });

    // Star rating logic
    const starContainers = document.querySelectorAll('.star-rating');
    starContainers.forEach(container => {
        const stars = container.querySelectorAll('.star');
        const ratingInput = container.querySelector('#ratingInput');
        if (stars.length && ratingInput) {
            let selectedRating = 0;
            function updateStars(rating) {
                stars.forEach(star => {
                    const value = parseInt(star.getAttribute('data-value'));
                    if (value <= rating) star.classList.add('filled');
                    else star.classList.remove('filled');
                });
            }
            stars.forEach(star => {
                star.addEventListener('click', function() {
                    const value = parseInt(this.getAttribute('data-value'));
                    selectedRating = value;
                    ratingInput.value = value;
                    updateStars(value);
                });
                star.addEventListener('mouseenter', function() {
                    const value = parseInt(this.getAttribute('data-value'));
                    updateStars(value);
                });
                star.addEventListener('mouseleave', function() {
                    updateStars(selectedRating);
                });
            });
        }
    });

    // Modal close
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });
    });

    // ===== THE MAGIC: Intersection Observer for animations =====
    const animateElements = document.querySelectorAll('.animate-on-scroll, .animate-slide-left, .animate-slide-right');
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target); // Stop observing once animated
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
        animateElements.forEach(el => observer.observe(el));
    } else {
        // Fallback for older browsers
        animateElements.forEach(el => el.classList.add('visible'));
    }
});

// Global modal functions
function showResponseModal(scopeId) {
    const modal = document.getElementById('responseModal');
    const form = document.getElementById('responseForm');
    if (modal && form) {
        form.action = '/scope/' + scopeId + '/respond';
        modal.style.display = 'flex';
    }
}
function closeModal() {
    const modal = document.getElementById('responseModal');
    if (modal) modal.style.display = 'none';
}
function toggleProviderFields() {
    const providerFields = document.getElementById('providerFields');
    if (providerFields) {
        const isProvider = document.querySelector('input[name="role"]:checked')?.value === 'provider';
        providerFields.style.display = isProvider ? 'block' : 'none';
    }
}