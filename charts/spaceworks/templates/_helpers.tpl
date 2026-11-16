{{- define "spaceworks.name" -}}
{{- printf "%s-spaceworks" .Release.Name | trunc 52 | trimSuffix "-" -}}
{{- end -}}
{{- define "spaceworks.backendImage" -}}
{{- $repository := .Values.backendImage -}}
{{- if and (eq .Values.deploymentMode "host") (empty .Values.backendDigest) -}}
{{- printf "%s:%s" $repository (required "imageTag is required for existing host releases" .Values.imageTag) -}}
{{- else -}}
{{- if not (regexMatch "^sha256:[a-f0-9]{64}$" .Values.backendDigest) -}}
{{- fail "backendDigest must pin a verified same-build OCI digest" -}}
{{- end -}}
{{- printf "%s@%s" $repository .Values.backendDigest -}}
{{- end -}}
{{- end -}}
{{- define "spaceworks.validate" -}}
{{- if not (has .Values.deploymentMode (list "host" "managed")) -}}{{- fail "deploymentMode must be host or managed" -}}{{- end -}}
{{- if ne .Values.deploymentProfile "full" -}}{{- fail "This chart is full only; use the qualified single-web free recipes" -}}{{- end -}}
{{- if not (has .Values.taskProfile (list "redis" "brokerless")) -}}{{- fail "taskProfile must be redis or brokerless" -}}{{- end -}}
{{- if eq .Values.deploymentMode "managed" -}}
{{- if and (eq .Values.taskProfile "redis") (or (ne .Values.scheduler "beat") (not .Values.beat.enabled)) -}}{{- fail "Redis requires exactly one beat" -}}{{- end -}}
{{- if and (eq .Values.taskProfile "brokerless") (or .Values.beat.enabled (not (has .Values.scheduler (list "loop" "external")))) -}}{{- fail "Brokerless requires beat disabled and loop or external scheduling" -}}{{- end -}}
{{- if not .Values.worker.enabled -}}{{- fail "Full requires persisted-work execution; do not omit the worker" -}}{{- end -}}
{{- end -}}
{{- end -}}
{{- define "spaceworks.podSecurity" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
{{- if eq .Values.deploymentMode "managed" }}
fsGroup: 10001
fsGroupChangePolicy: OnRootMismatch
{{- end }}
{{- end -}}
{{- define "spaceworks.env" -}}
- name: SPACEWORKS_DEPLOYMENT_MODE
  value: {{ .Values.deploymentMode | quote }}
- name: SPACEWORKS_DEPLOYMENT_PROFILE
  value: full
- name: CLOUD_TASK_PROFILE
  value: {{ .Values.taskProfile | quote }}
- name: CLOUD_SCHEDULER
  value: {{ .Values.scheduler | quote }}
- name: PORT
  value: "8000"
- name: GUNICORN_WORKERS
  value: {{ .Values.workers | quote }}
- name: CRON_INTERVAL_SECONDS
  value: "60"
- name: ROUTE_METRICS_ENABLED
  value: {{ .Values.routeMetricsEnabled | quote }}
- name: PROMETHEUS_MULTIPROC_DIR
  value: /run/metrics
{{- if eq .Values.deploymentMode "host" }}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ required "databasePointerSecret is required in host mode" .Values.databasePointerSecret | quote }}
      key: DATABASE_URL
- name: SPACEWORKS_DB_POINTER_GENERATION
  valueFrom:
    secretKeyRef:
      name: {{ .Values.databasePointerSecret | quote }}
      key: SPACEWORKS_DB_POINTER_GENERATION
- name: SPACEWORKS_HOST_MARKER_PATH
  value: /run/spaceworks-host/restore-marker.json
{{- end }}
{{- end -}}
{{- define "spaceworks.mounts" -}}
{{- if eq .Values.deploymentMode "host" }}
- name: host-gate
  mountPath: /run/spaceworks-host
  readOnly: true
{{- end }}
- name: metrics
  mountPath: /run/metrics
{{- if eq .Values.deploymentMode "managed" }}
- name: scratch
  mountPath: /tmp
{{- end }}
- name: celery
  mountPath: /var/lib/celery
{{- range .Values.configFiles }}
- name: {{ .name }}
  mountPath: {{ .mountPath | quote }}
  subPath: {{ .key | quote }}
  readOnly: true
{{- end }}
{{- end -}}
{{- define "spaceworks.volumes" -}}
{{- if eq .Values.deploymentMode "host" }}
- name: host-gate
  persistentVolumeClaim:
    claimName: {{ required "host mode requires prepared H1 authority; Recreate is not a recovery fence" .Values.hostGate.existingClaim | quote }}
    readOnly: true
{{- end }}
- name: metrics
  emptyDir: {}
- name: scratch
  emptyDir:
    sizeLimit: {{ .Values.scratchSize | quote }}
- name: celery
  emptyDir: {}
{{- include "spaceworks.configVolumes" . }}
{{- end -}}
{{- define "spaceworks.configVolumes" -}}
{{- range .Values.configFiles }}
- name: {{ .name }}
  secret:
    secretName: {{ .secretName | quote }}
    defaultMode: 0440
{{- end }}
{{- end -}}
