/* ==========================================================================
   VIDYA-X AI — Demo Mode Controller (Step 15)
   Provides 1-click presentation initialization with safe, isolated demo state.
   ========================================================================== */

window.VidyaDemo = {
  async initDemo() {
    if (!window.VidyaAPI) return;
    const btn = document.getElementById("demoToggleBtn");
    if (btn) btn.textContent = "Loading Demo Fixtures...";

    try {
      const res = await window.VidyaAPI.enableDemoMode();
      if (res.success) {
        window.location.reload();
      } else {
        alert(`Failed to initialize demo: ${res.error || "Unknown error"}`);
        if (btn) btn.textContent = "⚡ Launch Demo Mode";
      }
    } catch (err) {
      alert(`Demo activation error: ${err.message}`);
      if (btn) btn.textContent = "⚡ Launch Demo Mode";
    }
  },

  async resetDemo() {
    if (!confirm("Reset demo student and demo physics course? (Your real study materials will NOT be touched).")) {
      return;
    }
    try {
      const res = await window.VidyaAPI.resetDemoMode();
      if (res.success) {
        alert("Demo state successfully reset to default Newton Mechanics baseline.");
        window.location.reload();
      } else {
        alert(`Demo reset failed: ${res.error}`);
      }
    } catch (err) {
      alert(`Demo reset error: ${err.message}`);
    }
  },

  exitDemo() {
    window.VidyaAPI.disableDemoMode();
    window.location.reload();
  },
};
