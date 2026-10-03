(function () {
  "use strict";

  var videos = Array.prototype.slice.call(document.querySelectorAll("video"));
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!videos.length || reducedMotion.matches || !("IntersectionObserver" in window)) {
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var video = entry.target;
      if (entry.isIntersecting && entry.intersectionRatio >= 0.45) {
        video.play().catch(function () { /* Controls remain available if autoplay is blocked. */ });
      } else {
        video.pause();
      }
    });
  }, { threshold: [0, 0.45] });

  videos.forEach(function (video) {
    video.muted = true;
    observer.observe(video);
  });
}());
