// Mobile nav toggle
const menuToggle = document.querySelector(".menu-toggle");
const nav = document.querySelector(".nav");

if (menuToggle && nav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("open");
    menuToggle.classList.toggle("open", isOpen);
    menuToggle.setAttribute("aria-expanded", isOpen);
  });

  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("open");
      menuToggle.classList.remove("open");
      menuToggle.setAttribute("aria-expanded", "false");
    });
  });
}

// Scroll reveal
const revealEls = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window && revealEls.length) {
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
  );
  revealEls.forEach((el) => io.observe(el));
} else {
  revealEls.forEach((el) => el.classList.add("visible"));
}

// Gallery: lightbox
const galleryGrid = document.getElementById("gallery-grid");
if (galleryGrid) {
  const items = Array.from(galleryGrid.querySelectorAll(".gallery-item"));

  const lb = document.getElementById("lightbox");
  const lbImg = document.getElementById("lb-img");
  const lbCap = document.getElementById("lb-caption");
  const lbClose = lb && lb.querySelector(".lb-close");
  const lbPrev = lb && lb.querySelector(".lb-prev");
  const lbNext = lb && lb.querySelector(".lb-next");
  let currentIndex = -1;

  const openAt = (index) => {
    if (!items.length || !lb) return;
    currentIndex = ((index % items.length) + items.length) % items.length;
    const item = items[currentIndex];
    lbImg.src = item.getAttribute("href");
    lbImg.alt = item.querySelector("img").alt || "";
    lbCap.textContent = item.dataset.caption || "";
    lb.hidden = false;
    requestAnimationFrame(() => lb.classList.add("open"));
    document.body.style.overflow = "hidden";
  };

  const closeLb = () => {
    if (!lb) return;
    lb.classList.remove("open");
    setTimeout(() => { lb.hidden = true; lbImg.src = ""; }, 250);
    document.body.style.overflow = "";
    currentIndex = -1;
  };

  items.forEach((item, idx) => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      openAt(idx);
    });
  });

  if (lbClose) lbClose.addEventListener("click", closeLb);
  if (lbPrev) lbPrev.addEventListener("click", () => openAt(currentIndex - 1));
  if (lbNext) lbNext.addEventListener("click", () => openAt(currentIndex + 1));
  if (lb) lb.addEventListener("click", (e) => { if (e.target === lb) closeLb(); });
  document.addEventListener("keydown", (e) => {
    if (!lb || lb.hidden) return;
    if (e.key === "Escape") closeLb();
    if (e.key === "ArrowLeft") openAt(currentIndex - 1);
    if (e.key === "ArrowRight") openAt(currentIndex + 1);
  });
}
