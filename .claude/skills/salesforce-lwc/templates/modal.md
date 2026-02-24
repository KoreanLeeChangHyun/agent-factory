# 모달 컴포넌트 템플릿

## HTML (customModal.html)
```html
<template>
    <template lwc:if={isOpen}>
        <div class="modal-overlay" onclick={handleOverlayClick}>
            <div class="modal" onclick={stopPropagation} role="dialog" aria-modal="true">
                <!-- 헤더 -->
                <header class="modal-header">
                    <h2 class="modal-title">{title}</h2>
                    <button class="modal-close" onclick={handleClose} aria-label="Close">
                        &times;
                    </button>
                </header>

                <!-- 바디 -->
                <div class="modal-body">
                    <slot></slot>
                </div>

                <!-- 푸터 -->
                <template lwc:if={showFooter}>
                    <footer class="modal-footer">
                        <template lwc:if={showCancel}>
                            <button class="btn btn-secondary" onclick={handleCancel}>
                                {cancelLabel}
                            </button>
                        </template>
                        <button
                            class="btn btn-primary"
                            onclick={handleConfirm}
                            disabled={isConfirmDisabled}>
                            {confirmLabel}
                        </button>
                    </footer>
                </template>
            </div>
        </div>
    </template>
</template>
```

## JavaScript (customModal.js)
```javascript
import { LightningElement, api } from 'lwc';

export default class CustomModal extends LightningElement {
    @api title = 'Modal';
    @api confirmLabel = 'Confirm';
    @api cancelLabel = 'Cancel';
    @api showCancel = true;
    @api showFooter = true;
    @api closeOnOverlay = true;
    @api isConfirmDisabled = false;

    _isOpen = false;

    @api
    get isOpen() {
        return this._isOpen;
    }

    set isOpen(value) {
        this._isOpen = value;
        this.toggleBodyScroll(value);
    }

    // Public Methods
    @api
    open() {
        this._isOpen = true;
        this.toggleBodyScroll(true);
    }

    @api
    close() {
        this._isOpen = false;
        this.toggleBodyScroll(false);
    }

    // Private Methods
    toggleBodyScroll(disable) {
        if (disable) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    }

    stopPropagation(event) {
        event.stopPropagation();
    }

    // Event Handlers
    handleOverlayClick() {
        if (this.closeOnOverlay) {
            this.handleClose();
        }
    }

    handleClose() {
        this.dispatchEvent(new CustomEvent('close'));
        this.close();
    }

    handleCancel() {
        this.dispatchEvent(new CustomEvent('cancel'));
        this.close();
    }

    handleConfirm() {
        this.dispatchEvent(new CustomEvent('confirm'));
    }

    // Lifecycle
    connectedCallback() {
        this.handleKeyDown = this.handleKeyDown.bind(this);
        window.addEventListener('keydown', this.handleKeyDown);
    }

    disconnectedCallback() {
        window.removeEventListener('keydown', this.handleKeyDown);
        this.toggleBodyScroll(false);
    }

    handleKeyDown(event) {
        if (event.key === 'Escape' && this._isOpen) {
            this.handleClose();
        }
    }
}
```

## CSS (customModal.css)
```css
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.modal {
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    animation: slideIn 0.2s ease;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid #d8dde6;
}

.modal-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #333;
}

.modal-close {
    background: none;
    border: none;
    font-size: 28px;
    line-height: 1;
    color: #706e6b;
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: background-color 0.2s ease;
}

.modal-close:hover {
    background-color: #f4f6f9;
    color: #333;
}

.modal-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding: 1rem 1.5rem;
    border-top: 1px solid #d8dde6;
    background-color: #f4f6f9;
}

.btn {
    padding: 0.75rem 1.5rem;
    font-size: 14px;
    font-weight: 500;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.btn-primary {
    background-color: #0070d2;
    color: white;
}

.btn-primary:hover:not(:disabled) {
    background-color: #005fb2;
}

.btn-secondary {
    background-color: white;
    color: #333;
    border: 1px solid #d8dde6;
}

.btn-secondary:hover:not(:disabled) {
    background-color: #f4f6f9;
}

/* 크기 변형 */
:host(.modal-sm) .modal {
    max-width: 400px;
}

:host(.modal-lg) .modal {
    max-width: 800px;
}

:host(.modal-xl) .modal {
    max-width: 1140px;
}

/* 풀스크린 */
:host(.modal-fullscreen) .modal {
    max-width: none;
    width: 100%;
    height: 100%;
    max-height: none;
    border-radius: 0;
}
```

## 사용 예시

### 부모 컴포넌트 HTML
```html
<template>
    <button onclick={openModal}>Open Modal</button>

    <c-custom-modal
        title="Edit Account"
        confirm-label="Save"
        cancel-label="Cancel"
        lwc:ref="modal"
        onconfirm={handleSave}
        oncancel={handleCancel}
        onclose={handleClose}>

        <!-- 모달 내용 -->
        <c-custom-form lwc:ref="form"></c-custom-form>

    </c-custom-modal>
</template>
```

### 부모 컴포넌트 JS
```javascript
export default class ParentComponent extends LightningElement {
    openModal() {
        this.refs.modal.open();
    }

    handleSave() {
        // 폼 유효성 검사 및 저장
        const formData = this.refs.form.formData;
        // API 호출...
        this.refs.modal.close();
    }

    handleCancel() {
        // 취소 처리
    }

    handleClose() {
        // 닫기 처리
    }
}
```

### Confirm Dialog 변형
```html
<c-custom-modal
    title="Delete Confirmation"
    confirm-label="Delete"
    show-cancel={true}
    lwc:ref="confirmModal"
    onconfirm={handleDelete}>

    <p>Are you sure you want to delete this item?</p>
    <p class="text-muted">This action cannot be undone.</p>

</c-custom-modal>
```
