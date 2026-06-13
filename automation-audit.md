---
layout: default
title: Automation audit dashboard
permalink: /automation-audit/
description: Run-level audit dashboard for Glaucoma Data publication and press release automation.
---

{% assign audit = site.data.automation_audit %}
{% assign summary = audit.summary %}
{% assign latest_run = audit.runs | first %}

<section class="hero audit-index-hero">
  <h1>Automation Audit</h1>
  <p class="lead">This dashboard tracks expected source rosters, source-level terminal status, downloaded documents, press release rows, deferred review items, and run outcomes for weekly or on-demand archive automation. Generated {{ audit.generated_at_utc }}.</p>
</section>

<section class="summary-grid audit-summary-grid" aria-label="Automation audit summary">
  <div>
    <strong>Companies</strong>
    <span>{{ summary.in_scope_companies }}</span>
  </div>
  <div>
    <strong>Expected Sources</strong>
    <span>{{ summary.expected_sources }}</span>
  </div>
  <div>
    <strong>Pub Sources</strong>
    <span>{{ summary.publication_expected_sources }}</span>
  </div>
  <div>
    <strong>Press Sources</strong>
    <span>{{ summary.press_release_expected_sources }}</span>
  </div>
  <div>
    <strong>Latest Coverage</strong>
    <span>{{ summary.latest_checked_sources }} / {{ summary.latest_expected_sources }}</span>
  </div>
  <div>
    <strong>Latest Status</strong>
    <span>{{ summary.latest_run_status_label | default: summary.latest_run_status }}</span>
  </div>
  <div>
    <strong>Open Findings</strong>
    <span>{{ summary.open_findings }}</span>
  </div>
</section>

<section class="audit-panel">
  <h2>Latest Run</h2>
  {% if latest_run %}
    <dl class="metadata">
      <div>
        <dt>Run ID</dt>
        <dd><code>{{ latest_run.run_id }}</code></dd>
      </div>
      <div>
        <dt>Started</dt>
        <dd><code>{{ latest_run.started_at | default: "(not recorded)" }}</code></dd>
      </div>
      <div>
        <dt>Mode</dt>
        <dd>{% if latest_run.dry_run %}<span class="status-pill status-warning">Dry Run</span>{% else %}<span class="status-pill status-ok">Live Run</span>{% endif %}</dd>
      </div>
    </dl>
  {% else %}
    <p class="lead">No automation runs have been recorded yet. The expected source rosters below are ready, but a run must record expected sources and terminal source-status rows before coverage can be audited.</p>
  {% endif %}
</section>

<section>
  <h2>Coverage Findings</h2>
  {% if audit.findings.size == 0 %}
    <p class="lead">No open coverage findings. A valid no-change run still requires every expected non-skip source to have a terminal audit row.</p>
  {% else %}
    <table class="audit-table audit-wide-table">
      <thead>
        <tr>
          <th>Severity</th>
          <th>Type</th>
          <th>Company</th>
          <th>Source</th>
          <th>Detail</th>
        </tr>
      </thead>
      <tbody>
        {% for finding in audit.findings %}
          <tr>
            <td><span class="status-pill status-{{ finding.severity }}">{{ finding.severity_label | default: finding.severity }}</span></td>
            <td>
              {{ finding.kind_label | default: finding.kind }}
              {% if finding.error_kind_label and finding.error_kind_label != "" %}
                <br><span class="audit-subtle">{{ finding.error_kind_label }}</span>
              {% endif %}
            </td>
            <td>{{ finding.company }}</td>
            <td>{{ finding.source }}</td>
            <td>{{ finding.detail }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>

<section>
  <h2>Expected Source Roster</h2>
  <p class="lead">This roster lists monitored publication and press release sources for companies that already have collected documents. Every active row for the relevant automation type must appear in each run's terminal source-status ledger.</p>
  <table class="audit-table audit-wide-table">
    <thead>
      <tr>
        <th>Type</th>
        <th>Company</th>
        <th>Tier</th>
        <th>Kind</th>
        <th>Fetcher</th>
        <th>Source</th>
        <th>Mode</th>
      </tr>
    </thead>
    <tbody>
      {% for source in audit.expected_sources %}
        <tr>
          <td>{{ source.source_family_label | default: source.source_family }}</td>
          <td>{{ source.company_name }}</td>
          <td>{{ source.tier }}</td>
          <td>{{ source.source_kind_label | default: source.source_kind }}</td>
          <td>{{ source.fetcher_label | default: source.fetcher }}</td>
          <td>
            {% if source.source_url and source.source_url != "" %}
              <a href="{{ source.source_url }}" rel="noopener">{{ source.source_url }}</a>
            {% elsif source.pubmed_terms %}
              <code>{{ source.pubmed_terms | join: " OR " }}</code>
            {% else %}
              <span>{{ source.skip_reason | default: "(not configured)" }}</span>
            {% endif %}
          </td>
          <td>
            {% if source.status == "skipped_by_config" %}
              <span class="status-pill status-muted">Configured Skip</span>
            {% elsif source.discovery_only %}
              <span class="status-pill status-warning">Manual Retrieval</span>
            {% else %}
              <span class="status-pill status-ok">Automated</span>
            {% endif %}
          </td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</section>

<section>
  <h2>Automation Runs</h2>
  {% if audit.runs.size == 0 %}
    <p class="lead">No automation run records found.</p>
  {% else %}
    <table class="audit-table audit-wide-table">
      <thead>
        <tr>
          <th>Run</th>
          <th>Type</th>
          <th>Status</th>
          <th>Mode</th>
          <th>Started</th>
          <th>Coverage</th>
          <th>Downloads</th>
          <th>Press Rows</th>
          <th>Worklist</th>
          <th>Errors</th>
        </tr>
      </thead>
      <tbody>
        {% for run in audit.runs limit:25 %}
          <tr>
            <td><code>{{ run.run_id }}</code></td>
            <td>{{ run.run_type_label | default: run.run_type }}</td>
            <td><span class="status-pill status-{{ run.status }}">{{ run.status_label | default: run.status }}</span></td>
            <td>{% if run.dry_run %}<span class="status-pill status-warning">Dry Run</span>{% else %}<span class="status-pill status-ok">Live Run</span>{% endif %}</td>
            <td><code>{{ run.started_at }}</code></td>
            <td>{{ run.checked_sources_count }} / {{ run.expected_sources_count }}</td>
            <td>{{ run.downloaded_documents_count }}</td>
            <td>{{ run.new_press_releases_count }}</td>
            <td>{{ run.worklist_items_count }}</td>
            <td>{{ run.error_sources_count }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>

{% if latest_run %}
  <section>
    <h2>Latest Source Status</h2>
    <table class="audit-table audit-wide-table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Company</th>
          <th>Source</th>
          <th>Status</th>
          <th>Candidates</th>
          <th>New</th>
          <th>Downloads</th>
          <th>Worklist</th>
          <th>Error</th>
        </tr>
      </thead>
      <tbody>
        {% for source in latest_run.source_statuses %}
          <tr>
            <td>{{ source.source_family_label | default: source.source_family }}</td>
            <td>{{ source.company_name }}</td>
            <td>
              {% if source.source_url and source.source_url != "" %}
                <a href="{{ source.source_url }}" rel="noopener">{{ source.source_url }}</a>
              {% elsif source.pubmed_terms %}
                <code>{{ source.pubmed_terms | join: " OR " }}</code>
              {% else %}
                <span>{{ source.skip_reason | default: "(not configured)" }}</span>
              {% endif %}
            </td>
            <td><span class="status-pill status-{{ source.terminal_status }}">{{ source.terminal_status_label | default: source.terminal_status }}</span></td>
            <td>{{ source.candidate_count | default: "" }}</td>
            <td>{{ source.new_candidate_count | default: "" }}</td>
            <td>{{ source.downloaded_count | default: "" }}</td>
            <td>{{ source.worklist_count | default: "" }}</td>
            <td>{{ source.error }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>

  <section>
    <h2>New Document Traceability</h2>
    {% if latest_run.downloaded_documents.size == 0 %}
      <p class="lead">No downloaded document traceability rows were recorded for the latest automation run.</p>
    {% else %}
      <table class="audit-table audit-wide-table">
        <thead>
          <tr>
            <th>Title</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {% for document in latest_run.downloaded_documents %}
            <tr>
              <td>{{ document.title }}</td>
              <td>{% if document.source_url %}<a href="{{ document.source_url }}" rel="noopener">source</a>{% endif %}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </section>

  <section>
    <h2>New Press Release Rows</h2>
    {% if latest_run.new_press_releases.size == 0 %}
      <p class="lead">No new press release rows were recorded for the latest automation run.</p>
    {% else %}
      <table class="audit-table audit-wide-table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Title</th>
            <th>Date</th>
            <th>Program</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {% for release in latest_run.new_press_releases %}
            <tr>
              <td>{{ release.company | default: release.company_slug }}</td>
              <td>{{ release.title }}</td>
              <td><code>{{ release.date }}</code></td>
              <td>{{ release.program }}</td>
              <td>{% if release.source_url %}<a href="{{ release.source_url }}" rel="noopener">source</a>{% endif %}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </section>

  <section>
    <h2>Manual Worklist</h2>
    <p class="lead">This section lists items the latest run did not add automatically. In a dry run, it can include links that would be downloaded in a live run. In a live run, it should be limited to items that require review, access-controlled retrieval, or another manual step.</p>
    {% if latest_run.worklist_items.size == 0 %}
      <p class="lead">No manual retrieval items were recorded for the latest automation run.</p>
    {% else %}
      <table class="audit-table audit-wide-table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Title</th>
            <th>Reason</th>
            <th>URL</th>
          </tr>
        </thead>
        <tbody>
          {% for item in latest_run.worklist_items %}
            <tr>
              <td>{{ item.company | default: item.company_id }}</td>
              <td>{{ item.title }}</td>
              <td>{{ item.reason }}</td>
              <td>{% if item.url %}<a href="{{ item.url }}" rel="noopener">link</a>{% endif %}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% endif %}
  </section>

{% endif %}
