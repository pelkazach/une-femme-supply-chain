"use client"

import { useState, useCallback } from "react"
import { useDropzone } from "react-dropzone"
import { useMutation } from "@tanstack/react-query"
import { apiClient } from "@/lib/api-client"
import type { UploadResponse } from "@/lib/api-types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Upload, FileText, CheckCircle2, XCircle, Loader2 } from "lucide-react"

const ACCEPTED_TYPES = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
}

const MAX_SIZE = 10 * 1024 * 1024 // 10MB

const DISTRIBUTORS = [
  { value: "", label: "Auto-detect" },
  { value: "rndc", label: "RNDC" },
  { value: "southern_glazers", label: "Southern Glazers" },
  { value: "winebow", label: "Winebow" },
]

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [distributor, setDistributor] = useState("")
  const [progress, setProgress] = useState(0)
  const [fileError, setFileError] = useState<string | null>(null)

  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const { data } = await apiClient.post<UploadResponse>(
        "/upload",
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
          onUploadProgress: (e) => {
            if (e.total) {
              setProgress(Math.round((e.loaded * 100) / e.total))
            }
          },
        }
      )
      return data
    },
  })

  const onDrop = useCallback((acceptedFiles: File[], rejections: unknown[]) => {
    setFileError(null)
    if (rejections && (rejections as { errors: { code: string }[] }[]).length > 0) {
      const rej = rejections as { errors: { code: string }[] }[]
      const err = rej[0].errors[0]
      if (err.code === "file-too-large") {
        setFileError("File must be under 10MB")
      } else if (err.code === "file-invalid-type") {
        setFileError("Only CSV and Excel files accepted")
      } else {
        setFileError("Invalid file")
      }
      return
    }
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0])
      uploadMutation.reset()
      setProgress(0)
    }
  }, [uploadMutation])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE,
    multiple: false,
  })

  function handleUpload() {
    if (!file) return
    const formData = new FormData()
    formData.append("file", file)
    if (distributor) {
      formData.append("distributor", distributor)
    }
    uploadMutation.mutate(formData)
  }

  function handleReset() {
    setFile(null)
    setProgress(0)
    setFileError(null)
    uploadMutation.reset()
  }

  const result = uploadMutation.data?.result

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Distributor selector */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Distributor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <select
            value={distributor}
            onChange={(e) => setDistributor(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
          >
            {DISTRIBUTORS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </CardContent>
      </Card>

      {/* Drop zone */}
      <Card>
        <CardContent className="pt-6">
          <div
            {...getRootProps()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 text-center transition-colors",
              isDragActive
                ? "border-gold bg-gold/5"
                : "border-border hover:border-border-active",
              fileError && "border-destructive bg-destructive/5"
            )}
          >
            <input {...getInputProps()} />
            {file ? (
              <>
                <FileText className="mb-3 h-10 w-10 text-gold" />
                <p className="text-sm font-medium text-foreground">
                  {file.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </>
            ) : (
              <>
                <Upload className="mb-3 h-10 w-10 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">
                  {isDragActive
                    ? "Drop your file here"
                    : "Drag & drop a CSV or Excel file"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  or click to browse (max 10MB)
                </p>
              </>
            )}
          </div>

          {fileError && (
            <p className="mt-2 text-sm text-destructive">{fileError}</p>
          )}

          {/* Upload button & progress */}
          {file && !uploadMutation.isSuccess && (
            <div className="mt-4 space-y-3">
              {uploadMutation.isPending && (
                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                  <div
                    className="h-full rounded-full bg-gold transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              )}
              <Button
                onClick={handleUpload}
                disabled={uploadMutation.isPending}
                className="w-full bg-gold text-primary-foreground hover:bg-gold-hover"
              >
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading ({progress}%)
                  </>
                ) : (
                  "Upload File"
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Upload error */}
      {uploadMutation.isError && (
        <Card className="border-destructive/30">
          <CardContent className="flex items-center gap-3 pt-6">
            <XCircle className="h-5 w-5 text-destructive" />
            <div>
              <p className="text-sm font-medium text-foreground">
                Upload failed
              </p>
              <p className="text-xs text-muted-foreground">
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : "An unknown error occurred"}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Processing results */}
      {result && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Processing Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-3 rounded-lg border border-green-500/20 bg-green-500/10 px-4 py-3">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <div>
                  <p className="font-data text-xl font-semibold text-foreground">
                    {result.success_count}
                  </p>
                  <p className="text-xs text-muted-foreground">Rows imported</p>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3">
                <XCircle className="h-5 w-5 text-red-500" />
                <div>
                  <p className="font-data text-xl font-semibold text-foreground">
                    {result.error_count}
                  </p>
                  <p className="text-xs text-muted-foreground">Errors</p>
                </div>
              </div>
            </div>

            {/* Validation errors table */}
            {result.errors.length > 0 && (
              <div className="rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-surface">
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Row
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Field
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Error
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((err, i) => (
                      <tr
                        key={i}
                        className="border-b border-border last:border-0"
                      >
                        <td className="font-data px-3 py-2 text-foreground">
                          {err.row}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {err.field ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-foreground">
                          {err.message}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <Button variant="outline" onClick={handleReset} className="w-full">
              Upload Another File
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
