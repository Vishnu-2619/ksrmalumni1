document.addEventListener('DOMContentLoaded', function () {
    // Background Image Slideshow
    const images = [
        "https://www.ksrmce.ac.in/data1/images/s1.jpg",
        "https://www.ksrmce.ac.in/data1/images/s2.jpg",
        "https://www.ksrmce.ac.in/data1/images/alumni1.png",
        "https://www.ksrmce.ac.in/data1/images/s14.jpg"
    ];

    let currentIndex = 0;
    const backgroundSection = document.querySelector(".background-section");

    function changeBackground() {
        if (backgroundSection) {
            backgroundSection.style.backgroundImage = `url(${images[currentIndex]})`;
            backgroundSection.style.backgroundSize = "60%";
            backgroundSection.style.backgroundPosition = "center";
            backgroundSection.style.backgroundRepeat = "no-repeat";
            backgroundSection.style.transition = "background-image 1s ease-in-out";
            currentIndex = (currentIndex + 1) % images.length;
        }
    }

    // Set initial background and change every 5 seconds
    if (backgroundSection) {
        changeBackground();
        setInterval(changeBackground, 5000);
    }

    // Slider Functionality
    const slider = document.querySelector('.slider');
    const slides = document.querySelectorAll('.slide');
    let sliderIndex = 0;

    function nextSlide() {
        if (slides.length > 0) {
            sliderIndex = (sliderIndex + 1) % slides.length;
            updateSlider();
        }
    }

    function updateSlider() {
        if (slider) {
            slider.style.transform = `translateX(-${sliderIndex * 100}%)`;
            slider.style.transition = "transform 0.5s ease-in-out";
        }
    }

    // Start the slider if it exists
    if (slider && slides.length > 0) {
        setInterval(nextSlide, 3000);
    }

    // Fetch Alumni Data (if applicable)
    const alumniContainer = document.getElementById("alumni-list");
    if (alumniContainer) {
        fetch('http://127.0.0.1:5000/')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                console.log('Fetched alumni data:', data);
                alumniContainer.innerHTML = "";
                data.forEach(alumni => {
                    const alumniDiv = document.createElement("div");
                    alumniDiv.classList.add('profile-card'); // Use profile-card styling
                    alumniDiv.innerHTML = `
                        <div class="details">
                            <h3>${alumni.name}</h3>
                            <p><strong>Batch:</strong> ${alumni.batch || 'N/A'}</p>
                        </div>
                    `;
                    alumniContainer.appendChild(alumniDiv);
                });
            })
            .catch(error => {
                console.error('Error fetching alumni:', error);
                alumniContainer.innerHTML = "<p class='error'>Failed to load alumni data.</p>";
            });
    }

    // About More Button
    const aboutMoreBtn = document.getElementById('aboutMoreBtn');
    if (aboutMoreBtn) {
        aboutMoreBtn.addEventListener('click', function () {
            alert("More detailed information about KSRM Alumni Portal can be found on the About Us page.");
        });
    }

    // Event Modal Handling
    window.openEventModal = function (title, description) {
        const modal = document.getElementById('eventModal');
        if (modal) {
            document.getElementById('modalTitle').textContent = title;
            document.getElementById('modalDescription').textContent = description;
            modal.style.display = 'block';
        }
    };

    window.closeEventModal = function () {
        const modal = document.getElementById('eventModal');
        if (modal) {
            modal.style.display = 'none';
        }
    };

    // Generic Modal Handling
    const modals = document.querySelectorAll('.modal');
    const modalButtons = document.querySelectorAll('[id$="Btn"]'); // Buttons like myBtn, aboutMoreBtn, etc.
    const closeButtons = document.querySelectorAll('.close');

    modalButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            const modalId = this.id.replace('Btn', 'Modal'); // e.g., myBtn -> myModal
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.style.display = 'block';
            }
        });
    });

    closeButtons.forEach(span => {
        span.addEventListener('click', function () {
            const modal = this.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
        });
    });

    window.addEventListener('click', function (event) {
        modals.forEach(modal => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    });

    // Smooth Scrolling for Navigation Links
    document.querySelectorAll('nav a').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href.startsWith('#')) {
                e.preventDefault();
                const targetId = href.substring(1);
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    // Form Submission Feedback
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function (e) {
            const submitButton = this.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.textContent = 'Processing...';
                submitButton.classList.add('loading');
            }
        });
    });

    // Reset Button State on Page Load
    document.querySelectorAll('button[type="submit"]').forEach(button => {
        button.setAttribute('data-original-text', button.textContent);
    });

    window.addEventListener('load', () => {
        document.querySelectorAll('button[type="submit"]').forEach(button => {
            button.disabled = false;
            button.textContent = button.getAttribute('data-original-text');
            button.classList.remove('loading');
        });
    });

    // Input Field Focus Animation
    document.querySelectorAll('input, textarea').forEach(input => {
        input.addEventListener('focus', () => {
            input.style.borderColor = '#007bff';
            input.style.boxShadow = '0 0 8px rgba(0, 123, 255, 0.2)';
        });
        input.addEventListener('blur', () => {
            input.style.borderColor = '#ddd';
            input.style.boxShadow = 'none';
        });
    });

    // Confirmation for Dangerous Actions
    document.querySelectorAll('.btn-danger').forEach(button => {
        button.addEventListener('click', (e) => {
            const action = button.textContent.trim().toLowerCase();
            if (!confirm(`Are you sure you want to ${action} this item? This action cannot be undone.`)) {
                e.preventDefault();
            }
        });
    });

    // Scroll-to-Top Button
    const scrollToTopBtn = document.createElement('button');
    scrollToTopBtn.innerHTML = '↑';
    scrollToTopBtn.classList.add('scroll-to-top');
    document.body.appendChild(scrollToTopBtn);

    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            scrollToTopBtn.style.display = 'block';
        } else {
            scrollToTopBtn.style.display = 'none';
        }
    });

    scrollToTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // Fade-in Animation for Sections on Scroll
    const sections = document.querySelectorAll('.container, .event-section, .hero, .profile-card, .event-card');
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const sectionObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = 1;
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    sections.forEach(section => {
        section.style.opacity = 0;
        section.style.transform = 'translateY(30px)';
        section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        sectionObserver.observe(section);
    });
});