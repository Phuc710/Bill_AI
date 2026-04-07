package com.example.myapplication.ui.bills

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.isVisible
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.bumptech.glide.Glide
import com.example.myapplication.R
import com.example.myapplication.data.bootstrap.AppSessionStore
import com.example.myapplication.data.model.BillResponse
import com.example.myapplication.data.repository.BillRepository
import com.example.myapplication.databinding.ActivityBillDetailBinding
import com.example.myapplication.util.toCurrencyText
import com.example.myapplication.util.toEditorDateTime
import kotlinx.coroutines.launch

class BillDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityBillDetailBinding
    private val billRepository = BillRepository()
    private lateinit var itemsAdapter: BillItemsAdapter

    private lateinit var billId: String
    private var currentBill: BillResponse? = null
    private var currentUi: BillScreenUi? = null
    private var currentImageMode: BillImageMode = BillImageMode.CROPPED
    private var isEditMode = false
    private var shouldStartInEditMode = false
    private var hasAutoOpenedEditor = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportActionBar?.hide()

        binding = ActivityBillDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        billId = intent.getStringExtra(EXTRA_BILL_ID) ?: run {
            finish()
            return
        }
        shouldStartInEditMode = intent.getBooleanExtra(EXTRA_START_IN_EDIT_MODE, false)

        itemsAdapter = BillItemsAdapter()
        binding.rvItems.layoutManager = LinearLayoutManager(this)
        binding.rvItems.adapter = itemsAdapter

        setupActions()
        loadBillDetail()
    }

    private fun setupActions() {
        binding.btnBack.setOnClickListener { finish() }
        binding.btnRetry.setOnClickListener { loadBillDetail() }
        binding.btnShare.setOnClickListener { shareBill() }
        binding.btnDelete.setOnClickListener { confirmDelete() }
        binding.ivHeroImage.setOnClickListener { openImageViewer() }
        binding.tvImageHint.setOnClickListener { openImageViewer() }

        binding.btnModeCropped.setOnClickListener {
            currentImageMode = BillImageMode.CROPPED
            updateHeroImage()
        }
        binding.btnModeOriginal.setOnClickListener {
            currentImageMode = BillImageMode.ORIGINAL
            updateHeroImage()
        }

        binding.btnEdit.setOnClickListener { setEditMode(!isEditMode) }
        binding.btnSave.setOnClickListener { saveChanges() }
    }

    private fun loadBillDetail() {
        binding.layoutLoading.isVisible = true
        binding.layoutError.isVisible = false
        binding.scrollContent.isVisible = false

        lifecycleScope.launch {
            billRepository.getBillDetail(billId).fold(
                onSuccess = { bill ->
                    currentBill = bill
                    currentUi = BillScreenUiMapper.map(bill)
                    renderBill(bill)
                },
                onFailure = {
                    binding.layoutLoading.isVisible = false
                    binding.layoutError.isVisible = true
                    binding.scrollContent.isVisible = false
                }
            )
        }
    }

    private fun renderBill(bill: BillResponse) {
        val ui = currentUi ?: return

        binding.layoutLoading.isVisible = false
        binding.layoutError.isVisible = false
        binding.scrollContent.isVisible = true

        currentImageMode = ui.imageMode
        bindHero(ui)
        bindSummary(ui)
        bindReadOnly(ui)
        bindEditFields(BillEditDraft.fromBill(bill))

        val items = bill.items.orEmpty()
        itemsAdapter.submitList(items)
        binding.layoutEmptyItems.isVisible = items.isEmpty()
        binding.tvItemsSummary.text = ui.itemsSummaryText

        if ((shouldStartInEditMode || ui.needsAttention) && !hasAutoOpenedEditor) {
            hasAutoOpenedEditor = true
            setEditMode(true)
        } else {
            setEditMode(isEditMode)
        }
    }

    private fun bindHero(ui: BillScreenUi) {
        binding.tvStatusChip.text = ui.statusText
        if (ui.needsAttention) {
            binding.cardStatusChip.setCardBackgroundColor(Color.parseColor("#FFF4D6"))
            binding.tvStatusChip.setTextColor(Color.parseColor("#8A5800"))
        } else {
            binding.cardStatusChip.setCardBackgroundColor(Color.parseColor("#E8FFF4"))
            binding.tvStatusChip.setTextColor(Color.parseColor("#0D7A4E"))
        }

        binding.groupImageModes.isVisible = ui.supportsImageToggle
        updateHeroImage()
    }

    private fun bindSummary(ui: BillScreenUi) {
        binding.tvStoreName.text = ui.storeName
        binding.tvTotal.text = ui.totalText
        binding.tvQuickDate.text = ui.dateText
        binding.tvQuickAddress.text = ui.shortAddressText
        binding.tvTypeIcon.text = ui.typeUi.icon
        binding.tvCategory.text = ui.categoryText

        binding.cardReviewBanner.isVisible = ui.needsAttention
        binding.tvReviewBanner.text = currentBill?.message?.takeIf { it.isNotBlank() }
            ?: getString(R.string.detail_review_fallback)
    }

    private fun bindReadOnly(ui: BillScreenUi) {
        binding.tvMetaPrimary.text = listOf(
            ui.dateTimeText,
            ui.invoiceText.takeIf { it.isNotBlank() },
            ui.paymentText.takeIf { it.isNotBlank() }
        ).filterNotNull().joinToString(" • ")

        binding.tvMetaSecondary.text = listOf(
            ui.fullAddressText.takeIf { it.isNotBlank() },
            ui.phoneText.takeIf { it.isNotBlank() }
        ).filterNotNull().joinToString("\n").ifBlank {
            getString(R.string.detail_address_empty)
        }

        binding.tvCashMeta.text = getString(
            R.string.detail_money_summary,
            ui.subtotalText,
            ui.cashGivenText,
            ui.cashChangeText
        )

        val note = ui.noteText.takeIf { it.isNotBlank() }
        binding.tvNoteValue.isVisible = note != null
        binding.tvNoteValue.text = note
    }

    private fun bindEditFields(draft: BillEditDraft) {
        binding.etStoreName.setText(draft.storeName)
        binding.etDateTime.setText(draft.dateTime.toEditorDateTime())
        binding.etTotal.setText(draft.totalAmount?.toString().orEmpty())
        binding.etAddress.setText(draft.address)
        binding.etPhone.setText(draft.phone)
        binding.etInvoiceId.setText(draft.invoiceId)
        binding.etPayment.setText(draft.paymentMethod)
        binding.etCategory.setText(draft.category.ifBlank { "Khác" })
        binding.etNote.setText(draft.note)
    }

    private fun updateHeroImage() {
        val ui = currentUi ?: return
        val imageUrl = when (currentImageMode) {
            BillImageMode.CROPPED -> ui.croppedImageUrl ?: ui.originalImageUrl
            BillImageMode.ORIGINAL -> ui.originalImageUrl ?: ui.croppedImageUrl
        }
        binding.btnModeCropped.isChecked = currentImageMode == BillImageMode.CROPPED
        binding.btnModeOriginal.isChecked = currentImageMode == BillImageMode.ORIGINAL

        Glide.with(this)
            .load(imageUrl)
            .centerCrop()
            .into(binding.ivHeroImage)
    }

    private fun openImageViewer() {
        val ui = currentUi ?: return
        if (ui.croppedImageUrl.isNullOrBlank() && ui.originalImageUrl.isNullOrBlank()) return

        BillImageViewerDialog.show(
            host = supportFragmentManager,
            croppedUrl = ui.croppedImageUrl,
            originalUrl = ui.originalImageUrl,
            initialMode = currentImageMode
        )
    }

    private fun setEditMode(enabled: Boolean) {
        isEditMode = enabled
        binding.layoutReadOnly.isVisible = !enabled
        binding.layoutEditForm.isVisible = enabled
        binding.btnSave.isEnabled = enabled
        binding.btnEdit.text = getString(
            if (enabled) R.string.detail_cancel_edit else R.string.detail_edit
        )
    }

    private fun saveChanges() {
        val draft = BillEditDraft(
            storeName = binding.etStoreName.text?.toString()?.trim().orEmpty(),
            address = binding.etAddress.text?.toString()?.trim().orEmpty(),
            phone = binding.etPhone.text?.toString()?.trim().orEmpty(),
            invoiceId = binding.etInvoiceId.text?.toString()?.trim().orEmpty(),
            paymentMethod = binding.etPayment.text?.toString()?.trim().orEmpty(),
            totalAmount = binding.etTotal.text?.toString()?.trim()?.toLongOrNull(),
            dateTime = binding.etDateTime.text?.toString()?.trim().orEmpty(),
            category = binding.etCategory.text?.toString()?.trim().orEmpty(),
            note = binding.etNote.text?.toString()?.trim().orEmpty()
        )

        if (draft.storeName.isBlank()) {
            binding.etStoreName.error = getString(R.string.placeholder_store)
            return
        }

        binding.btnSave.isEnabled = false

        lifecycleScope.launch {
            billRepository.updateBill(billId, draft.toPayload()).fold(
                onSuccess = {
                    AppSessionStore.invalidate()
                    Toast.makeText(
                        this@BillDetailActivity,
                        getString(R.string.detail_save_success),
                        Toast.LENGTH_SHORT
                    ).show()
                    setEditMode(false)
                    loadBillDetail()
                },
                onFailure = {
                    binding.btnSave.isEnabled = true
                    Toast.makeText(
                        this@BillDetailActivity,
                        getString(R.string.detail_save_failed),
                        Toast.LENGTH_LONG
                    ).show()
                }
            )
        }
    }

    private fun shareBill() {
        val ui = currentUi ?: return
        val summary = listOf(ui.storeName, ui.dateTimeText, ui.totalText).joinToString("\n")
        startActivity(
            Intent.createChooser(
                Intent(Intent.ACTION_SEND).apply {
                    type = "text/plain"
                    putExtra(Intent.EXTRA_TEXT, summary)
                },
                getString(R.string.detail_share_title)
            )
        )
    }

    private fun confirmDelete() {
        AlertDialog.Builder(this)
            .setTitle(R.string.detail_delete_title)
            .setMessage(R.string.detail_delete_message)
            .setPositiveButton(R.string.detail_delete_confirm) { _, _ ->
                lifecycleScope.launch {
                    billRepository.deleteBill(billId).fold(
                        onSuccess = {
                            AppSessionStore.invalidate()
                            finish()
                        },
                        onFailure = {
                            Toast.makeText(
                                this@BillDetailActivity,
                                getString(R.string.detail_delete_failed),
                                Toast.LENGTH_SHORT
                            ).show()
                        }
                    )
                }
            }
            .setNegativeButton(R.string.detail_delete_cancel, null)
            .show()
    }

    companion object {
        const val EXTRA_BILL_ID = "extra_bill_id"
        private const val EXTRA_START_IN_EDIT_MODE = "extra_start_in_edit_mode"

        fun createIntent(
            context: Context,
            billId: String,
            startInEditMode: Boolean = false
        ): Intent {
            return Intent(context, BillDetailActivity::class.java)
                .putExtra(EXTRA_BILL_ID, billId)
                .putExtra(EXTRA_START_IN_EDIT_MODE, startInEditMode)
        }
    }
}
