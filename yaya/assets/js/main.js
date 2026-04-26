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

// Gallery: missing-image fallback, filtering, lightbox
const galleryGrid = document.getElementById("gallery-grid");
if (galleryGrid) {
  const items = Array.from(galleryGrid.querySelectorAll(".gallery-item"));

  // Mostra il fallback elegante quando il file foto non esiste
  items.forEach((item) => {
    const img = item.querySelector("img");
    if (!img) return;
    const markMissing = () => item.classList.add("img-missing");
    if (img.complete) {
      if (!img.naturalWidth) markMissing();
    } else {
      img.addEventListener("error", markMissing);
      img.addEventListener("load", () => {
        if (!img.naturalWidth) markMissing();
      });
    }
  });

  // Filtri categoria
  const filterBtns = document.querySelectorAll(".gf-btn");
  const emptyMsg = document.getElementById("gallery-empty");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const filter = btn.dataset.filter;
      filterBtns.forEach((b) => b.classList.toggle("active", b === btn));
      let visible = 0;
      items.forEach((item) => {
        const match = filter === "all" || item.dataset.category === filter;
        item.classList.toggle("is-hidden", !match);
        if (match) visible++;
      });
      if (emptyMsg) emptyMsg.hidden = visible > 0;
    });
  });

  // Lightbox
  const lb = document.getElementById("lightbox");
  const lbImg = document.getElementById("lb-img");
  const lbCap = document.getElementById("lb-caption");
  const lbClose = lb && lb.querySelector(".lb-close");
  const lbPrev = lb && lb.querySelector(".lb-prev");
  const lbNext = lb && lb.querySelector(".lb-next");
  let currentIndex = -1;

  const visibleItems = () => items.filter((i) => !i.classList.contains("is-hidden") && !i.classList.contains("img-missing"));

  const openAt = (index) => {
    const list = visibleItems();
    if (!list.length || !lb) return;
    currentIndex = ((index % list.length) + list.length) % list.length;
    const item = list[currentIndex];
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

  items.forEach((item) => {
    item.addEventListener("click", (e) => {
      // Solo se la foto esiste — altrimenti lascia il link inerte
      if (item.classList.contains("img-missing")) { e.preventDefault(); return; }
      e.preventDefault();
      const list = visibleItems();
      const idx = list.indexOf(item);
      if (idx >= 0) openAt(idx);
    });
  });

  if (lbClose) lbClose.addEventListener("click", closeLb);
  if (lbPrev) lbPrev.addEventListener("click", () => openAt(currentIndex - 1));
  if (lbNext) lbNext.addEventListener("click", () => openAt(currentIndex + 1));
  if (lb) lb.addEventListener("click", (e) => { if (e.target === lb) closeLb(); });
  document.addEventListener("keydown", (e) => {
    if (lb && lb.hidden) return;
    if (e.key === "Escape") closeLb();
    if (e.key === "ArrowLeft") openAt(currentIndex - 1);
    if (e.key === "ArrowRight") openAt(currentIndex + 1);
  });
}
