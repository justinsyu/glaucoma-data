---
layout: default
title: ClinicalTrials.gov updates
permalink: /clinical-trials/
description: ClinicalTrials.gov snapshot ledger for trials related to treatments tracked in the Glaucoma Data Archive.
---

{% assign ctgov = site.data.clinicaltrials_updates %}
{% assign summary = ctgov.summary %}

<section class="hero">
  <h1>ClinicalTrials.gov updates</h1>
  <p class="lead">ClinicalTrials.gov records for investigational glaucoma treatments tracked in this archive. The seed roster is refreshed from the ClinicalTrials.gov v2 API when the data generator runs.</p>
</section>

<section class="summary-grid audit-summary-grid clinical-trials-summary-grid" aria-label="ClinicalTrials.gov monitor summary">
  <div>
    <strong>Sources</strong>
    <span>{{ summary.monitored_sources }}</span>
  </div>
  <div>
    <strong>Tracked Trials</strong>
    <span>{{ summary.tracked_trials }}</span>
  </div>
  <div>
    <strong>Total Updates</strong>
    <span>{{ summary.updates_total }}</span>
  </div>
  <div>
    <strong>Last 7 Days</strong>
    <span>{{ summary.updates_last_7_days }}</span>
  </div>
  <div>
    <strong>Latest Trial Update</strong>
    <span>{{ summary.most_recent_registry_update_date | default: "None" }}</span>
  </div>
  <div>
    <strong>Last Checked</strong>
    <span>{% if summary.latest_capture_at %}{{ summary.latest_capture_at | date: "%Y-%m-%d" }}{% else %}None{% endif %}</span>
  </div>
</section>

<section class="audit-panel">
  <h2>Monitoring Contract</h2>
  <p class="lead">The monitor uses the ClinicalTrials.gov v2 studies API and exports retained trial metadata to this page. No schedule is configured here; run the watcher manually before enabling any automation.</p>
</section>

<section>
  <h2>Most Recent Trial Update</h2>
  {% if ctgov.most_recent_registry_updates.trials.size == 0 %}
    <p class="lead">No ClinicalTrials.gov last-update date is available in the retained baseline.</p>
  {% else %}
    <p class="lead">Most recent CT.gov last-update-posted date among tracked trials: <code>{{ ctgov.most_recent_registry_updates.date }}</code>. The table below lists the tracked trial records with that date and the retained update details available for each record.</p>
    <table class="audit-table audit-wide-table clinical-trials-table">
      <thead>
        <tr>
          <th>Company</th>
          <th>Treatment</th>
          <th>NCT ID</th>
          <th>Status</th>
          <th>Results</th>
          <th>Update Details</th>
          <th>Trial</th>
        </tr>
      </thead>
      <tbody>
        {% for trial in ctgov.most_recent_registry_updates.trials %}
          <tr>
            <td>{{ trial.company }}</td>
            <td>{{ trial.program }}</td>
            <td class="nct-id"><a href="{{ trial.trial_url }}" rel="noopener">{{ trial.nct_id }}</a></td>
            <td>{{ trial.overall_status | replace: "_", " " }}</td>
            <td>{% if trial.has_results %}Yes{% else %}No{% endif %}</td>
            <td>
              <ul class="audit-detail-list">
                {% for detail in trial.update_details %}
                  <li><strong>{{ detail.label }}:</strong> {{ detail.value }}</li>
                {% endfor %}
              </ul>
            </td>
            <td>{{ trial.trial_title }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>

<section>
  <h2>Weekly Updates</h2>
  {% if ctgov.weekly_buckets.size == 0 %}
    <p class="lead">No weekly updates have been generated yet.</p>
  {% else %}
    <table class="audit-table audit-wide-table">
      <thead>
        <tr>
          <th>Week</th>
          <th>Updates</th>
          <th>New Trials</th>
          <th>Record Updates</th>
          <th>Removed Trials</th>
        </tr>
      </thead>
      <tbody>
        {% for week in ctgov.weekly_buckets limit:12 %}
          <tr>
            <td><code>{{ week.week_start }}</code> to <code>{{ week.week_end }}</code></td>
            <td>{{ week.update_count }}</td>
            <td>{{ week.new_trials }}</td>
            <td>{{ week.updated_trials }}</td>
            <td>{{ week.removed_trials }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>

<section>
  <h2>Recent Updates</h2>
  {% if ctgov.updates.size == 0 %}
    <p class="lead">No changes have been detected across retained CT.gov snapshots yet.</p>
  {% else %}
    <table class="audit-table audit-wide-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Company</th>
          <th>Treatment</th>
          <th>NCT ID</th>
          <th>Trial</th>
          <th>Changed Fields</th>
          <th>Last Update Posted</th>
        </tr>
      </thead>
      <tbody>
        {% for update in ctgov.updates limit:100 %}
          <tr>
            <td><code>{{ update.detected_date }}</code></td>
            <td><span class="status-pill status-{{ update.event_type }}">{{ update.event_type_label }}</span></td>
            <td>{{ update.company }}</td>
            <td>{{ update.program }}</td>
            <td><a href="{{ update.trial_url }}" rel="noopener">{{ update.nct_id }}</a></td>
            <td>{{ update.trial_title }}</td>
            <td>
              {% if update.changed_fields.size > 0 %}
                {% assign labels = update.changed_fields | map: "label" %}
                {{ labels | join: ", " }}
              {% else %}
                <span class="audit-subtle">Record membership</span>
              {% endif %}
            </td>
            <td><code>{{ update.last_update_post_date | default: "" }}</code></td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>

<section>
  <h2>Current Trial Roster</h2>
  <table class="audit-table audit-wide-table clinical-trials-table">
    <thead>
      <tr>
        <th>Company</th>
        <th>Treatment</th>
        <th>NCT ID</th>
        <th>Status</th>
        <th>Results</th>
        <th>Registry Updated</th>
        <th>Trial</th>
      </tr>
    </thead>
    <tbody>
      {% for trial in ctgov.latest_trials limit:200 %}
        <tr>
          <td>{{ trial.company }}</td>
          <td>{{ trial.program }}</td>
          <td class="nct-id"><a href="{{ trial.trial_url }}" rel="noopener">{{ trial.nct_id }}</a></td>
          <td>{{ trial.overall_status | replace: "_", " " }}</td>
          <td>{% if trial.has_results %}Yes{% else %}No{% endif %}</td>
          <td><code>{{ trial.last_update_post_date | default: "" }}</code></td>
          <td>{{ trial.trial_title }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</section>
