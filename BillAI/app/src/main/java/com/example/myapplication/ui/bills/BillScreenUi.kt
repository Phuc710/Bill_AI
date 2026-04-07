package com.example.myapplication.ui.bills

import com.example.myapplication.data.model.BillItem
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.util.toCurrencyText
import com.example.myapplication.util.toDisplayDate
import com.example.myapplication.util.toDisplayDateTime
import java.util.Locale

enum class BillImageMode {
    CROPPED,
    ORIGINAL
}

enum class BillType {
    FOOD,
    SHOPPING,
    TRANSPORT,
    UTILITY,
    HEALTH,
    SERVICE,
    OTHER
}

data class BillTypeUi(
    val type: BillType,
    val label: String,
    val icon: String
)

data class BillScreenUi(
    val storeName: String,
    val totalText: String,
    val dateTimeText: String,
    val dateText: String,
    val shortAddressText: String,
    val fullAddressText: String,
    val phoneText: String,
    val invoiceText: String,
    val paymentText: String,
    val subtotalText: String,
    val cashGivenText: String,
    val cashChangeText: String,
    val noteText: String,
    val categoryText: String,
    val statusText: String,
    val needsAttention: Boolean,
    val itemsSummaryText: String,
    val imageMode: BillImageMode,
    val croppedImageUrl: String?,
    val originalImageUrl: String?,
    val supportsImageToggle: Boolean,
    val typeUi: BillTypeUi
)

private interface BillTypeResolver {
    fun matches(category: String, items: List<BillItem>, storeName: String): Boolean
    fun create(category: String): BillTypeUi
}

private object FoodBillResolver : BillTypeResolver {
    override fun matches(category: String, items: List<BillItem>, storeName: String): Boolean {
        val haystack = buildString {
            append(category)
            append(' ')
            append(storeName)
            append(' ')
            append(items.joinToString(" ") { it.name })
        }.lowercase(Locale.getDefault())
        return haystack.contains("ăn") ||
            haystack.contains("uong") ||
            haystack.contains("uống") ||
            haystack.contains("quán") ||
            haystack.contains("bbq") ||
            haystack.contains("cafe") ||
            haystack.contains("trà") ||
            haystack.contains("cơm") ||
            haystack.contains("bún") ||
            haystack.contains("phở")
    }

    override fun create(category: String): BillTypeUi {
        return BillTypeUi(BillType.FOOD, category.ifBlank { "Ăn uống" }, "🍜")
    }
}

private object ShoppingBillResolver : BillTypeResolver {
    override fun matches(category: String, items: List<BillItem>, storeName: String): Boolean {
        val haystack = "$category $storeName".lowercase(Locale.getDefault())
        return haystack.contains("mua sắm") || haystack.contains("shop") || haystack.contains("mart")
    }

    override fun create(category: String): BillTypeUi {
        return BillTypeUi(BillType.SHOPPING, category.ifBlank { "Mua sắm" }, "🛍")
    }
}

private object TransportBillResolver : BillTypeResolver {
    override fun matches(category: String, items: List<BillItem>, storeName: String): Boolean {
        val haystack = "$category $storeName".lowercase(Locale.getDefault())
        return haystack.contains("di chuyển") || haystack.contains("xăng") || haystack.contains("grab")
    }

    override fun create(category: String): BillTypeUi {
        return BillTypeUi(BillType.TRANSPORT, category.ifBlank { "Di chuyển" }, "🚗")
    }
}

private object UtilityBillResolver : BillTypeResolver {
    override fun matches(category: String, items: List<BillItem>, storeName: String): Boolean {
        val haystack = "$category $storeName".lowercase(Locale.getDefault())
        return haystack.contains("điện") || haystack.contains("nuoc") || haystack.contains("nước")
    }

    override fun create(category: String): BillTypeUi {
        return BillTypeUi(BillType.UTILITY, category.ifBlank { "Tiện ích" }, "💡")
    }
}

private object HealthBillResolver : BillTypeResolver {
    override fun matches(category: String, items: List<BillItem>, storeName: String): Boolean {
        val haystack = "$category $storeName".lowercase(Locale.getDefault())
        return haystack.contains("y tế") || haystack.contains("thuốc") || haystack.contains("pharmacy")
    }

    override fun create(category: String): BillTypeUi {
        return BillTypeUi(BillType.HEALTH, category.ifBlank { "Y tế" }, "💊")
    }
}

private object ServiceBillResolver : BillTypeResolver {
    override fun matches(category: String, items: List<BillItem>, storeName: String): Boolean {
        val haystack = "$category $storeName".lowercase(Locale.getDefault())
        return haystack.contains("dịch vụ") || haystack.contains("service")
    }

    override fun create(category: String): BillTypeUi {
        return BillTypeUi(BillType.SERVICE, category.ifBlank { "Dịch vụ" }, "🧰")
    }
}

object BillScreenUiMapper {
    private val resolvers = listOf(
        FoodBillResolver,
        ShoppingBillResolver,
        TransportBillResolver,
        UtilityBillResolver,
        HealthBillResolver,
        ServiceBillResolver
    )

    fun map(bill: BillResponse): BillScreenUi {
        val items = bill.items.orEmpty()
        val category = bill.data?.category.orEmpty()
        val storeName = bill.data?.store_name.orEmpty()
        val typeUi = resolvers.firstOrNull { it.matches(category, items, storeName) }
            ?.create(category)
            ?: BillTypeUi(BillType.OTHER, category.ifBlank { "Hóa đơn" }, "🏷")

        val supportsImageToggle = !bill.cropped_image_url.isNullOrBlank() &&
            !bill.original_image_url.isNullOrBlank() &&
            bill.cropped_image_url != bill.original_image_url

        return BillScreenUi(
            storeName = storeName.ifBlank { "Hóa đơn" },
            totalText = bill.data?.total.toCurrencyText(),
            dateTimeText = bill.data?.datetime.toDisplayDateTime(),
            dateText = bill.data?.datetime.toDisplayDate(),
            shortAddressText = bill.data?.address.toShortAddress(),
            fullAddressText = bill.data?.address.orEmpty(),
            phoneText = bill.data?.phone.orEmpty(),
            invoiceText = bill.data?.invoice_id.orEmpty(),
            paymentText = bill.data?.payment_method.orEmpty(),
            subtotalText = bill.data?.subtotal.toCurrencyText(),
            cashGivenText = bill.data?.cash_given.toCurrencyText(),
            cashChangeText = bill.data?.cash_change.toCurrencyText(),
            noteText = bill.message.orEmpty(),
            categoryText = typeUi.label,
            statusText = when {
                bill.status.equals("failed", true) -> "Cần chỉnh sửa"
                else -> "Hoàn tất"
            },
            needsAttention = bill.status.equals("failed", true),
            itemsSummaryText = "${items.size} món",
            imageMode = if (!bill.cropped_image_url.isNullOrBlank()) BillImageMode.CROPPED else BillImageMode.ORIGINAL,
            croppedImageUrl = bill.cropped_image_url,
            originalImageUrl = bill.original_image_url,
            supportsImageToggle = supportsImageToggle,
            typeUi = typeUi
        )
    }
}

private fun String?.toShortAddress(): String {
    if (this.isNullOrBlank()) return "Chưa có địa chỉ"
    val parts = split(",").map { it.trim() }.filter { it.isNotBlank() }
    return when {
        parts.size >= 2 -> parts.takeLast(2).joinToString(", ")
        else -> this
    }
}
