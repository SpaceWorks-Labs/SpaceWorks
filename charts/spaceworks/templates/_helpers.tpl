{{- define "spaceworks.name" -}}
{{- printf "%s-spaceworks" .Release.Name | trunc 52 | trimSuffix "-" -}}
{{- end -}}
{{- define "spaceworks.backendImage" -}}
{{- printf "%s:%s" .Values.backendImage (required "imageTag must pin a release" .Values.imageTag) -}}
{{- end -}}
{{- define "spaceworks.podSecurity" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
{{- end -}}
{{- define "spaceworks.env" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ required "databasePointerSecret required" .Values.databasePointerSecret | quote }}
      key: DATABASE_URL
- name: SPACEWORKS_DB_POINTER_GENERATION
  valueFrom:
    secretKeyRef:
      name: {{ .Values.databasePointerSecret | quote }}
      key: SPACEWORKS_DB_POINTER_GENERATION
- name: SPACEWORKS_HOST_MARKER_PATH
  value: /run/spaceworks-host/restore-marker.json
- name: ROUTE_METRICS_ENABLED
  value: {{ .Values.routeMetricsEnabled | quote }}
- name: PROMETHEUS_MULTIPROC_DIR
  value: /run/metrics
{{- end -}}
{{- define "spaceworks.mounts" -}}
- name: host-gate
  mountPath: /run/spaceworks-host
  readOnly: true
- name: metrics
  mountPath: /run/metrics
- name: celery
  mountPath: /var/lib/celery
{{- end -}}
{{- define "spaceworks.volumes" -}}
- name: host-gate
  persistentVolumeClaim:
    claimName: {{ required "hostGate.existingClaim must contain operator-provisioned H1 state" .Values.hostGate.existingClaim | quote }}
    readOnly: true
- name: metrics
  emptyDir: {}
- name: celery
  emptyDir: {}
{{- end -}}

{{- define "spaceworks.beatVolumes" -}}
- name: host-gate
  persistentVolumeClaim:
    claimName: {{ required "hostGate.existingClaim is required" .Values.hostGate.existingClaim | quote }}
    readOnly: true
- name: metrics
  emptyDir: {}
- name: celery
  persistentVolumeClaim:
    claimName: {{ required "beat.existingClaim must preserve the scheduler state" .Values.beat.existingClaim | quote }}
{{- end -}}
