const activityList = document.querySelector("#activity-list");

if (activityList && Array.isArray(mockActivities)) {
  activityList.innerHTML = mockActivities.map((activity) => `
    <article class="activity-card">
      <div class="card-body">
        <span class="tag">${activity.category}</span>
        <h3>${activity.title}</h3>
        <p>${activity.description}</p>
        <div class="card-meta">${activity.time} · ${activity.location}</div>
      </div>
    </article>
  `).join("");
}
