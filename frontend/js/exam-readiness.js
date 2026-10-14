/**
 * VIDYA-X AI — Exam Readiness Tracker Logic (Step 12)
 */

const API_BASE_URL = 'http://localhost:8000/api';

function getActiveProfile() {
  const saved = localStorage.getItem('vidyaXProfile');
  if (saved) {
    try {
      const p = JSON.parse(saved);
      return {
        studentId: p.studentId || 'demo_student',
        courseId: p.courseId || p.course_name || 'cs101_algo',
      };
    } catch (e) {
      console.error('Failed to parse profile', e);
    }
  }
  return { studentId: 'demo_student', courseId: 'cs101_algo' };
}

document.addEventListener('DOMContentLoaded', () => {
  fetchExamReadiness();
});

async function fetchExamReadiness() {
  const profile = getActiveProfile();

  try {
    const res = await fetch(`${API_BASE_URL}/learner/${encodeURIComponent(profile.studentId)}/course/${encodeURIComponent(profile.courseId)}/exam-readiness`);
    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}`);
    }

    const data = await res.json();
    if (data.success) {
      renderCategoryCard(data);
      renderTopicCoverage(data);
      renderActionPlan(data);
      renderWeakTopics(data);
    }
  } catch (err) {
    console.error('Failed to fetch exam readiness:', err);
    document.getElementById('readinessCategoryCard').innerHTML = `
      <div class="empty-state">
        <p>⚡ Could not load exam readiness evaluation.</p>
      </div>`;
  }
}

function renderCategoryCard(data) {
  const container = document.getElementById('readinessCategoryCard');
  const cat = data.readiness_category || 'insufficient_data';
  const label = data.category_label || 'Insufficient Data';
  const desc = data.category_description || 'No evaluation available.';

  const avgPct = Math.round((data.average_mastery || 0) * 100);
  const covPct = Math.round(data.topic_coverage_percentage || 0);

  container.innerHTML = `
    <div class="category-main">
      <span class="category-tag cat-${cat}">${label}</span>
      <h3 class="category-title">${label}</h3>
      <p class="category-desc">${escapeHtml(desc)}</p>
      <div style="margin-top: 0.75rem; font-size: 0.85rem; color: #94a3b8;">
        <span>Evidence Confidence: <strong style="color: #cbd5e1; text-transform: uppercase;">${data.confidence_indicator || 'low'}</strong></span>
        ${data.days_until_exam !== null ? `<span style="margin-left: 1rem;">⏳ Exam in: <strong>${data.days_until_exam} days</strong></span>` : ''}
      </div>
    </div>
    <div class="category-stats">
      <div class="stat-box">
        <div class="stat-num">${avgPct}%</div>
        <div class="stat-lbl">Avg Mastery</div>
      </div>
      <div class="stat-box">
        <div class="stat-num">${covPct}%</div>
        <div class="stat-lbl">Coverage</div>
      </div>
      <div class="stat-box">
        <div class="stat-num">${data.total_attempts_count || 0}</div>
        <div class="stat-lbl">Attempts</div>
      </div>
    </div>
  `;
}

function renderTopicCoverage(data) {
  const container = document.getElementById('topicCoverageList');
  container.innerHTML = '';

  const covered = data.covered_topics || [];
  const weak = data.topics_needing_attention || [];

  if (covered.length === 0 && weak.length === 0) {
    container.innerHTML = `<p style="font-size: 0.9rem; color: #94a3b8;">No topics available yet.</p>`;
    return;
  }

  // Combine covered and weak lists
  const allTopicsMap = new Map();
  covered.forEach(name => allTopicsMap.set(name, { name, mastery: 0.85, status: 'Mastered' }));
  weak.forEach(t => allTopicsMap.set(t.topic_name, { name: t.topic_name, mastery: t.mastery_probability, status: 'Needs Review' }));

  allTopicsMap.forEach(item => {
    const row = document.createElement('div');
    row.className = 'topic-row';

    const mPct = Math.round(item.mastery * 100);

    row.innerHTML = `
      <span class="topic-name">${escapeHtml(item.name)}</span>
      <div class="topic-bar-wrapper">
        <div class="mini-bar-bg">
          <div class="mini-bar-fill" style="width: ${mPct}%; background: ${mPct >= 70 ? '#10b981' : (mPct >= 50 ? '#f59e0b' : '#ef4444')};"></div>
        </div>
        <span style="font-size: 0.85rem; font-weight: 700; color: #f8fafc;">${mPct}%</span>
      </div>
    `;

    container.appendChild(row);
  });
}

function renderActionPlan(data) {
  const container = document.getElementById('actionPlanContainer');
  container.innerHTML = '';

  const steps = data.suggested_next_steps || [];
  if (steps.length === 0) {
    container.innerHTML = `<p style="font-size: 0.9rem; color: #94a3b8;">No specific action items.</p>`;
    return;
  }

  steps.forEach(step => {
    const item = document.createElement('div');
    item.className = 'step-item';
    item.innerHTML = `
      <span class="step-icon">🎯</span>
      <span>${escapeHtml(step)}</span>
    `;
    container.appendChild(item);
  });
}

function renderWeakTopics(data) {
  const container = document.getElementById('weakTopicsContainer');
  container.innerHTML = '';

  const weak = data.topics_needing_attention || [];
  if (weak.length === 0) {
    container.innerHTML = `<p style="font-size: 0.9rem; color: #34d399; font-weight: 600;">🎉 Great job! No topics currently marked as weak.</p>`;
    return;
  }

  weak.forEach(item => {
    const card = document.createElement('div');
    card.style.cssText = 'background: #0f172a; border: 1px solid #334155; border-left: 4px solid #ef4444; border-radius: 8px; padding: 0.8rem 1rem; margin-bottom: 0.75rem;';

    const mPct = Math.round(item.mastery_probability * 100);
    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
        <strong style="color: #f8fafc; font-size: 0.95rem;">${escapeHtml(item.topic_name)}</strong>
        <span style="font-size: 0.8rem; color: #f87171; font-weight: 700;">${mPct}% Mastery</span>
      </div>
      <p style="font-size: 0.85rem; color: #94a3b8; margin: 0;">${escapeHtml(item.reason)}</p>
    `;

    container.appendChild(card);
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
