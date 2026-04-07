package com.example.myapplication.util

import com.example.myapplication.data.model.BillSummary
import java.text.Normalizer
import java.text.NumberFormat
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale

private val vietnameseLocale = Locale.forLanguageTag("vi-VN")
private val currencyFormatter = NumberFormat.getNumberInstance(vietnameseLocale)
private val displayDateFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy", vietnameseLocale)
private val displayDateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy • HH:mm", vietnameseLocale)
private val editorDateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm", vietnameseLocale)
private val backendDateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss", Locale.US)

private val supportedDateTimePatterns = listOf(
    "dd/MM/yyyy HH:mm:ss",
    "dd/MM/yyyy HH:mm",
    "dd-MM-yyyy HH:mm:ss",
    "dd-MM-yyyy HH:mm",
    "yyyy-MM-dd HH:mm:ss",
    "yyyy-MM-dd HH:mm",
    "yyyy-MM-dd'T'HH:mm:ss"
).map { DateTimeFormatter.ofPattern(it, vietnameseLocale) }

private val supportedDatePatterns = listOf(
    "dd/MM/yyyy",
    "dd-MM-yyyy",
    "yyyy-MM-dd"
).map { DateTimeFormatter.ofPattern(it, vietnameseLocale) }

fun Long?.toCurrencyText(suffix: String = "đ"): String {
    val safeAmount = this ?: 0L
    return "${currencyFormatter.format(safeAmount)}$suffix"
}

fun Double?.toProcessingTimeText(): String {
    val safeValue = this ?: 0.0
    return if (safeValue >= 1000) {
        String.format(Locale.US, "%.1fs", safeValue / 1000.0)
    } else {
        "${safeValue.toInt()}ms"
    }
}

fun String?.toDisplayDate(): String {
    val parsedDateTime = parseFlexibleDateTime(this) ?: return this.rawFallback("Chưa rõ ngày")
    return parsedDateTime.toLocalDate().format(displayDateFormatter)
}

fun String?.toDisplayDateTime(): String {
    val parsedDateTime = parseFlexibleDateTime(this) ?: return this.rawFallback("Chưa rõ thời gian")
    return parsedDateTime.format(displayDateTimeFormatter)
}

fun String?.toEditorDateTime(): String {
    val parsedDateTime = parseFlexibleDateTime(this) ?: return this.orEmpty()
    return parsedDateTime.format(editorDateTimeFormatter)
}

fun String?.toBackendDateTime(): String? {
    val parsedDateTime = parseFlexibleDateTime(this) ?: return null
    return parsedDateTime.format(backendDateTimeFormatter)
}

fun BillSummary.matchesMonth(yearMonth: YearMonth): Boolean {
    val parsedDate = parseFlexibleDateTime(created_at)?.toLocalDate() ?: return false
    return YearMonth.from(parsedDate) == yearMonth
}

fun BillSummary.statusLabel(): String {
    return when {
        status.equals("failed", ignoreCase = true) -> "Thất bại"
        status.equals("completed", ignoreCase = true) -> "Hoàn tất"
        else -> status.replaceFirstChar { it.titlecase(Locale.getDefault()) }
    }
}

fun BillSummary.matchesSearchQuery(query: String): Boolean {
    if (query.isBlank()) return true

    val normalizedQuery = query.normalizeForSearch()
    val searchableFields = listOfNotNull(
        store_name,
        invoice_number,
        payment_method,
        created_at,
        issued_at,
        created_at.toDisplayDate(),
        issued_at.toDisplayDate()
    )

    return searchableFields.any { field ->
        field.normalizeForSearch().contains(normalizedQuery)
    }
}

private fun parseFlexibleDateTime(value: String?): LocalDateTime? {
    if (value.isNullOrBlank()) return null

    runCatching { return OffsetDateTime.parse(value).toLocalDateTime() }
    runCatching { return LocalDateTime.parse(value) }

    supportedDateTimePatterns.forEach { formatter ->
        runCatching { return LocalDateTime.parse(value, formatter) }
    }

    supportedDatePatterns.forEach { formatter ->
        runCatching { return LocalDate.parse(value, formatter).atStartOfDay() }
    }

    return null
}

private fun String.normalizeForSearch(): String {
    val normalized = Normalizer.normalize(lowercase(Locale.getDefault()), Normalizer.Form.NFD)
        .replace("\\p{M}+".toRegex(), "")
        .replace("đ", "d")
    return normalized
        .replace("/", "")
        .replace("-", "")
        .replace(" ", "")
        .trim()
}

private fun String?.rawFallback(defaultValue: String): String {
    if (this.isNullOrBlank()) return defaultValue
    return substringBefore("T").ifBlank { this }
}
