package com.example.myapplication.util

import com.example.myapplication.data.model.BillSummary
import java.text.NumberFormat
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale

private val currencyFormatter = NumberFormat.getNumberInstance(Locale.forLanguageTag("vi-VN"))
private val displayDateFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy", Locale.forLanguageTag("vi-VN"))
private val dateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy • HH:mm", Locale.forLanguageTag("vi-VN"))

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
    if (this.isNullOrBlank()) return "Chưa rõ ngày"
    return runCatching { OffsetDateTime.parse(this).format(displayDateFormatter) }
        .recoverCatching { displayDateFormatter.format(LocalDateTime.parse(this)) }
        .getOrElse { rawFallbackDate(this) }
}

fun String?.toDisplayDateTime(): String {
    if (this.isNullOrBlank()) return "Chưa rõ thời gian"
    return runCatching { OffsetDateTime.parse(this).format(dateTimeFormatter) }
        .recoverCatching { dateTimeFormatter.format(LocalDateTime.parse(this)) }
        .getOrElse { rawFallbackDate(this) }
}

fun BillSummary.matchesMonth(yearMonth: YearMonth): Boolean {
    val parsedDate = runCatching { OffsetDateTime.parse(created_at).toLocalDate() }
        .recoverCatching { LocalDateTime.parse(created_at).toLocalDate() }
        .getOrNull()
        ?: return false
    return YearMonth.from(parsedDate) == yearMonth
}

fun BillSummary.statusLabel(): String {
    return when {
        status.equals("failed", ignoreCase = true) -> "Thất bại"
        needs_review -> "Cần kiểm tra"
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

private fun String.normalizeForSearch(): String {
    return lowercase(Locale.getDefault())
        .replace("đ", "d")
        .replace("/", "")
        .replace("-", "")
        .replace(" ", "")
        .trim()
}

private fun rawFallbackDate(value: String): String {
    return value.substringBefore("T").ifBlank { value }
}
