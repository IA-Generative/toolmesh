{{/*
Expand the name of the chart.
*/}}
{{- define "helm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "helm.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "helm.labels" -}}
app.kubernetes.io/name: {{ include "helm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "helm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "helm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Name and selector labels of the datetime MCP server.
*/}}
{{- define "helm.mcpDatetime.fullname" -}}
{{- printf "%s-mcp-datetime" (include "helm.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "helm.mcpDatetime.selectorLabels" -}}
app.kubernetes.io/name: {{ include "helm.name" . }}-mcp-datetime
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Name of the Secret holding the OIDC client secret used for token exchange.
*/}}
{{- define "helm.oidcSecretName" -}}
{{- default (printf "%s-oidc" (include "helm.fullname" .) | trunc 63 | trimSuffix "-") .Values.oidc.clientSecret.existingSecret }}
{{- end }}
