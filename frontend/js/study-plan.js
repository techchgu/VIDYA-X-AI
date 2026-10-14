/**
 * VIDYA-X AI — Smart Study Planner & Spaced Repetition Logic (Step 12)
 */

const API_BASE_URL = 'http://localhost:8000/api';

// Helper to get active student and course profile from localStorage
function getActiveProfile() {
  const saved = localStorage.getItem('vidyaXProfile');
  if (saved) {
    try {
      const p = JSON.parse(saved);
      return {
        studentId: p.studentId || 'demo_student',
        courseId: p.courseId || p.course_id || 'cs101_algo',
        courseName: p.courseName || p.course_name || 'General Course',
        examDate: p.examDate || p.exam_date || '',
        dailyBudget: p.dailyStudyTime || p.daily_minutes_budget || 45,
      };
    } catch (e) {
      console.error('Failed to parse vidyaXProfile', e);
    }
  }
  return {
    studentId: 'demo_student',
    courseId: 'cs101_algo',
    courseName: 'General Course',
    examDate: '',
    dailyBudget: 45,
  };
}

let activePlanData = null;
let currentViewMode = 'today'; // 'today' | 'week'

document.addEventListener('DOMContentLoaded', () => {
  const profile = getActiveProfile();

  // Populate inputs with stored profile defaults
  document.getElementById('courseIdInput').value = profile.courseId;
  document.getElementById('dailyBudgetInput').value = profile.dailyBudget;
  if (profile.examDate) {
    document.getElementById('examDateInput').value = profile.examDate;
  }

  // Event Listeners
  document.getElementById('toggleConfigBtn').addEventListener('click', () => {
    document.getElementById('planConfigPanel').classList.toggle('hidden');
  });

  document.getElementById('generatePlanBtn').addEventListener('click', () => {
    document.getElementById('planConfigPanel').classList.remove('hidden');
  });

  document.getElementById('savePrefsBtn').addEventListener('click', handleSavePreferences);
  document.getElementById('confirmGenerateBtn').addEventListener('click', handleGeneratePlan);

  document.getElementById('todayViewTab').addEventListener('click', () => {
    currentViewMode = 'today';
    document.getElementById('todayViewTab').classList.add('active');
    document.getElementById('weekViewTab').classList.remove('active');
    renderScheduleView();
  });

  document.getElementById('weekViewTab').addEventListener('click', () => {
    currentViewMode = 'week';
    document.getElementById('weekViewTab').classList.add('active');
    document.getElementById('todayViewTab').classList.remove('active');
    renderScheduleView();
  });

  // Initial fetch
  fetchActiveStudyPlan();
});

async function fetchActiveStudyPlan() {
  const profile = getActiveProfile();
  const container = document.getElementById('scheduleContainer');
  container.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading your study plan...</p>
    </div>`;

  try {
    const res = await fetch(`${API_BASE_URL}/learner/${encodeURIComponent(profile.studentId)}/course/${encodeURIComponent(profile.courseId)}/study-plan`);
    if (!res.ok) {
      if (res.status === 404) {
        renderNoPlanState();
        return;
      }
      throw new Error(`HTTP error ${res.status}`);
    }

    const data = await res.json();
    if (data.success && data.plan_id) {
      activePlanData = data;
      updateSummaryMetrics(data);
      renderScheduleView();
    } else {
      renderNoPlanState();
    }
  } catch (err) {
    console.error('Failed to load study plan:', err);
    container.innerHTML = `
      <div class="empty-state">
        <p>⚡ Could not load active study plan.</p>
        <button onclick="handleGeneratePlan()" class="btn btn-primary" style="margin-top: 1rem;">Generate Study Plan</button>
      </div>`;
  }
}

function updateSummaryMetrics(data) {
  const examMetric = document.getElementById('examDateMetric');
  const budgetMetric = document.getElementById('budgetMetric');
  const progressMetric = document.getElementById('progressMetric');
  const progressFill = document.getElementById('planProgressBarFill');
  const taskCountMetric = document.getElementById('taskCountMetric');

  if (data.exam_date) {
    const exDate = new Date(data.exam_date);
    examMetric.textContent = exDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } else {
    examMetric.textContent = 'Not Scheduled';
  }

  budgetMetric.textContent = `${data.daily_minutes_budget || 45} mins / day`;
  const pct = data.completion_percentage || 0;
  progressMetric.textContent = `${pct}%`;
  progressFill.style.width = `${pct}%`;
  taskCountMetric.textContent = `${data.completed_tasks || 0} / ${data.total_tasks || 0}`;
}

function renderNoPlanState() {
  const container = document.getElementById('scheduleContainer');
  container.innerHTML = `
    <div class="empty-state">
      <h3>✨ No Active Study Plan Found</h3>
      <p>Generate a personalized study plan to optimize your daily practice, flashcard reviews, and exam preparation.</p>
      <button onclick="handleGeneratePlan()" class="btn btn-primary" style="margin-top: 1rem;">Generate Plan Now</button>
    </div>`;
}

function renderScheduleView() {
  if (!activePlanData || !activePlanData.days || activePlanData.days.length === 0) {
    renderNoPlanState();
    return;
  }

  const container = document.getElementById('scheduleContainer');
  container.innerHTML = '';

  const todayStr = new Date().toISOString().split('T')[0];

  let daysToDisplay = activePlanData.days;
  if (currentViewMode === 'today') {
    daysToDisplay = activePlanData.days.filter(d => d.scheduled_date === todayStr);
    if (daysToDisplay.length === 0) {
      // Fallback to first day if today is not in plan horizon
      daysToDisplay = [activePlanData.days[0]];
    }
  }

  daysToDisplay.forEach(day => {
    const dayCard = document.createElement('div');
    dayCard.className = 'day-card';

    const isToday = day.scheduled_date === todayStr;
    const dateFormatted = new Date(day.scheduled_date + 'T00:00:00Z').toLocaleDateString(undefined, {
      weekday: 'long',
      month: 'short',
      day: 'numeric',
    });

    const badgeClass = `badge-${day.status || 'pending'}`;

    dayCard.innerHTML = `
      <div class="day-header">
        <div class="day-title">${dateFormatted} ${isToday ? '🌟 (Today)' : ''}</div>
        <div>
          <span class="day-badge ${badgeClass}">${day.status || 'pending'}</span>
          <span style="font-size: 0.85rem; color: #94a3b8; margin-left: 0.5rem;">⏱️ ${day.planned_minutes} mins</span>
        </div>
      </div>
      <div class="task-list" id="taskList_${day.day_id}"></div>
    `;

    container.appendChild(dayCard);
    const taskListEl = dayCard.querySelector(`#taskList_${day.day_id}`);

    if (!day.tasks || day.tasks.length === 0) {
      taskListEl.innerHTML = `<p style="font-size: 0.9rem; color: #64748b;">No study tasks scheduled for this day.</p>`;
      return;
    }

    day.tasks.forEach(task => {
      const taskCard = document.createElement('div');
      const isCompleted = task.status === 'completed';
      taskCard.className = `task-card priority-${task.priority_level || 'medium'} ${isCompleted ? 'task-completed' : ''}`;

      const actionBtnText = getActionButtonText(task.task_type);

      taskCard.innerHTML = `
        <div class="task-info">
          <div class="task-top-row">
            <span class="task-type-badge">${formatTaskType(task.task_type)}</span>
            <span class="priority-pill pill-${task.priority_level || 'medium'}">${(task.priority_level || 'medium').toUpperCase()} PRIORITY</span>
            <span style="font-size: 0.8rem; color: #94a3b8;">${task.topic_name}</span>
          </div>
          <h4 class="task-title">${escapeHtml(task.title)}</h4>
          <p class="task-desc">${escapeHtml(task.description || '')}</p>
          <div class="task-meta">
            <span>⏱️ Estimated: ${task.estimated_minutes} mins</span>
            ${task.priority_reason ? `<span>💡 Why: ${escapeHtml(task.priority_reason)}</span>` : ''}
          </div>
        </div>
        <div class="task-actions">
          ${!isCompleted ? `<button onclick="handleLaunchTask('${task.task_type}', '${task.resource_id || ''}', '${task.topic_id || ''}')" class="btn-sm btn-action">${actionBtnText}</button>` : ''}
          ${!isCompleted ? `<button onclick="handleCompleteTask('${task.task_id}')" class="btn-sm btn-complete">✓ Complete</button>` : `<span style="font-size: 0.8rem; color: #34d399; font-weight: 700;">✓ Completed</span>`}
          ${!isCompleted ? `<button onclick="handleSkipTask('${task.task_id}')" class="btn-sm btn-skip">Skip</button>` : ''}
        </div>
      `;

      taskListEl.appendChild(taskCard);
    });
  });
}

function formatTaskType(ttype) {
  const map = {
    flashcard_review: '🎴 Flashcards',
    weak_topic_revision: '📖 Revision',
    revision_material_read: '📄 Study Guide',
    adaptive_quiz: '🎯 Adaptive Quiz',
    remediation_activity: '🛠️ Remediation',
    prerequisite_review: '🧩 Prerequisite',
    mixed_practice: '✍️ Practice',
    self_assessment: '📝 Diagnostic',
  };
  return map[ttype] || ttype;
}

function getActionButtonText(ttype) {
  if (ttype === 'flashcard_review') return 'Review Cards';
  if (ttype === 'weak_topic_revision' || ttype === 'revision_material_read') return 'Read Material';
  if (ttype === 'adaptive_quiz' || ttype === 'mixed_practice' || ttype === 'self_assessment') return 'Start Quiz';
  if (ttype === 'remediation_activity') return 'Start Remediation';
  return 'Start Activity';
}

function handleLaunchTask(taskType, resourceId, topicId) {
  if (taskType === 'flashcard_review') {
    window.location.href = 'flashcards.html';
  } else if (taskType === 'weak_topic_revision' || taskType === 'revision_material_read' || taskType === 'prerequisite_review') {
    window.location.href = 'revision.html';
  } else if (taskType === 'remediation_activity') {
    window.location.href = 'remediation.html';
  } else {
    window.location.href = 'quiz.html';
  }
}

async function handleGeneratePlan() {
  const profile = getActiveProfile();
  const courseId = document.getElementById('courseIdInput').value.trim() || profile.courseId;
  const horizon = parseInt(document.getElementById('horizonSelect').value, 10) || 7;
  const budget = parseInt(document.getElementById('dailyBudgetInput').value, 10) || 45;
  const examDate = document.getElementById('examDateInput').value || null;

  const container = document.getElementById('scheduleContainer');
  container.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Generating your personalized adaptive study plan...</p>
    </div>`;

  try {
    const res = await fetch(`${API_BASE_URL}/study-plan/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: profile.studentId,
        course_id: courseId,
        horizon_days: horizon,
        daily_minutes_budget: budget,
        exam_date: examDate,
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      activePlanData = data;
      document.getElementById('planConfigPanel').classList.add('hidden');
      updateSummaryMetrics(data);
      renderScheduleView();
    } else {
      alert(`Plan generation failed: ${data.error || 'Unknown error'}`);
      fetchActiveStudyPlan();
    }
  } catch (err) {
    console.error('Failed to generate study plan:', err);
    alert('Error generating study plan.');
    fetchActiveStudyPlan();
  }
}

async function handleSavePreferences() {
  const profile = getActiveProfile();
  const courseId = document.getElementById('courseIdInput').value.trim() || profile.courseId;
  const budget = parseInt(document.getElementById('dailyBudgetInput').value, 10) || 45;
  const examDate = document.getElementById('examDateInput').value || null;

  try {
    const res = await fetch(`${API_BASE_URL}/learner/${encodeURIComponent(profile.studentId)}/course/${encodeURIComponent(courseId)}/study-preferences`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        daily_minutes_budget: budget,
        exam_date: examDate,
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      alert('Study preferences saved successfully!');
    } else {
      alert(`Failed to save preferences: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    console.error('Save preferences failed:', err);
    alert('Error saving preferences.');
  }
}

async function handleCompleteTask(taskId) {
  const profile = getActiveProfile();
  try {
    const res = await fetch(`${API_BASE_URL}/study-plan/tasks/${taskId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: profile.studentId,
        actual_minutes: 15,
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      fetchActiveStudyPlan();
    } else {
      alert(`Could not complete task: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    console.error('Failed to complete task:', err);
  }
}

async function handleSkipTask(taskId) {
  const profile = getActiveProfile();
  try {
    const res = await fetch(`${API_BASE_URL}/study-plan/tasks/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: profile.studentId,
        status: 'skipped',
      }),
    });

    const data = await res.json();
    if (res.ok && data.success) {
      fetchActiveStudyPlan();
    } else {
      alert(`Could not skip task: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    console.error('Failed to skip task:', err);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
