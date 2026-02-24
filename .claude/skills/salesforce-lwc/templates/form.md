# 폼 컴포넌트 템플릿

## HTML (customForm.html)
```html
<template>
    <form class="form" onsubmit={handleSubmit}>
        <!-- 텍스트 입력 -->
        <div class="form-group">
            <label class="form-label" for="name">
                Name <span class="required">*</span>
            </label>
            <input
                type="text"
                id="name"
                class={nameInputClass}
                value={formData.name}
                data-field="name"
                onchange={handleInputChange}
                onblur={handleBlur}
                placeholder="Enter name"
                required>
            <template lwc:if={errors.name}>
                <span class="form-error">{errors.name}</span>
            </template>
        </div>

        <!-- 이메일 입력 -->
        <div class="form-group">
            <label class="form-label" for="email">
                Email <span class="required">*</span>
            </label>
            <input
                type="email"
                id="email"
                class={emailInputClass}
                value={formData.email}
                data-field="email"
                onchange={handleInputChange}
                onblur={handleBlur}
                placeholder="Enter email"
                required>
            <template lwc:if={errors.email}>
                <span class="form-error">{errors.email}</span>
            </template>
        </div>

        <!-- 셀렉트 박스 -->
        <div class="form-group">
            <label class="form-label" for="type">Type</label>
            <select
                id="type"
                class="form-select"
                data-field="type"
                onchange={handleInputChange}>
                <option value="">-- Select --</option>
                <template for:each={typeOptions} for:item="option">
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                </template>
            </select>
        </div>

        <!-- 체크박스 -->
        <div class="form-group">
            <label class="form-checkbox">
                <input
                    type="checkbox"
                    checked={formData.isActive}
                    data-field="isActive"
                    onchange={handleCheckboxChange}>
                <span class="checkbox-label">Active</span>
            </label>
        </div>

        <!-- 텍스트에어리어 -->
        <div class="form-group">
            <label class="form-label" for="description">Description</label>
            <textarea
                id="description"
                class="form-textarea"
                value={formData.description}
                data-field="description"
                onchange={handleInputChange}
                rows="4"
                placeholder="Enter description"></textarea>
        </div>

        <!-- 버튼 -->
        <div class="form-actions">
            <button type="submit" class="btn btn-primary" disabled={isSubmitting}>
                <template lwc:if={isSubmitting}>
                    Saving...
                </template>
                <template lwc:else>
                    Save
                </template>
            </button>
            <button type="button" class="btn btn-secondary" onclick={handleReset}>
                Reset
            </button>
        </div>
    </form>
</template>
```

## JavaScript (customForm.js)
```javascript
import { LightningElement, api } from 'lwc';

export default class CustomForm extends LightningElement {
    @api recordId;

    // Note: Spring '20 이후 모든 필드는 기본 반응형.
    // 객체/배열 내부 속성 변경 감지를 위해 새 객체 할당 패턴 사용.
    formData = {
        name: '',
        email: '',
        type: '',
        isActive: false,
        description: ''
    };

    errors = {};

    isSubmitting = false;
    touched = {};

    typeOptions = [
        { label: 'Customer', value: 'customer' },
        { label: 'Partner', value: 'partner' },
        { label: 'Prospect', value: 'prospect' }
    ];

    // Getters for dynamic classes
    get nameInputClass() {
        return this.errors.name ? 'form-input error' : 'form-input';
    }

    get emailInputClass() {
        return this.errors.email ? 'form-input error' : 'form-input';
    }

    get isValid() {
        return Object.keys(this.errors).length === 0;
    }

    // Event Handlers
    handleInputChange(event) {
        const field = event.target.dataset.field;
        const value = event.target.value;

        this.formData = {
            ...this.formData,
            [field]: value
        };

        if (this.touched[field]) {
            this.validateField(field, value);
        }
    }

    handleCheckboxChange(event) {
        const field = event.target.dataset.field;
        const checked = event.target.checked;

        this.formData = {
            ...this.formData,
            [field]: checked
        };
    }

    handleBlur(event) {
        const field = event.target.dataset.field;
        const value = event.target.value;

        this.touched[field] = true;
        this.validateField(field, value);
    }

    validateField(field, value) {
        const newErrors = { ...this.errors };

        switch (field) {
            case 'name':
                if (!value || value.trim() === '') {
                    newErrors.name = 'Name is required';
                } else if (value.length < 2) {
                    newErrors.name = 'Name must be at least 2 characters';
                } else {
                    delete newErrors.name;
                }
                break;

            case 'email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!value || value.trim() === '') {
                    newErrors.email = 'Email is required';
                } else if (!emailRegex.test(value)) {
                    newErrors.email = 'Please enter a valid email';
                } else {
                    delete newErrors.email;
                }
                break;

            default:
                break;
        }

        this.errors = newErrors;
    }

    validateAll() {
        this.touched = { name: true, email: true };
        this.validateField('name', this.formData.name);
        this.validateField('email', this.formData.email);
        return this.isValid;
    }

    async handleSubmit(event) {
        event.preventDefault();

        if (!this.validateAll()) {
            return;
        }

        this.isSubmitting = true;

        try {
            // API 호출 또는 이벤트 발생
            this.dispatchEvent(new CustomEvent('submit', {
                detail: { ...this.formData }
            }));
        } catch (error) {
            console.error('Submit error:', error);
        } finally {
            this.isSubmitting = false;
        }
    }

    handleReset() {
        this.formData = {
            name: '',
            email: '',
            type: '',
            isActive: false,
            description: ''
        };
        this.errors = {};
        this.touched = {};
    }

    // Public Methods
    @api
    setFormData(data) {
        this.formData = { ...this.formData, ...data };
    }

    @api
    reset() {
        this.handleReset();
    }
}
```

## CSS (customForm.css)
```css
:host {
    display: block;
}

.form {
    max-width: 600px;
}

.form-group {
    margin-bottom: 1.25rem;
}

.form-label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 14px;
    font-weight: 500;
    color: #333;
}

.required {
    color: #c23934;
}

.form-input,
.form-select,
.form-textarea {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 14px;
    line-height: 1.5;
    color: #333;
    background-color: white;
    border: 1px solid #d8dde6;
    border-radius: 4px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
    outline: none;
    border-color: #0070d2;
    box-shadow: 0 0 0 3px rgba(0, 112, 210, 0.15);
}

.form-input.error,
.form-select.error,
.form-textarea.error {
    border-color: #c23934;
}

.form-input.error:focus,
.form-select.error:focus,
.form-textarea.error:focus {
    box-shadow: 0 0 0 3px rgba(194, 57, 52, 0.15);
}

.form-error {
    display: block;
    margin-top: 0.25rem;
    font-size: 12px;
    color: #c23934;
}

.form-checkbox {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
}

.form-checkbox input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
}

.checkbox-label {
    font-size: 14px;
    color: #333;
}

.form-textarea {
    resize: vertical;
    min-height: 100px;
}

.form-actions {
    display: flex;
    gap: 0.75rem;
    margin-top: 1.5rem;
}

.btn {
    padding: 0.75rem 1.5rem;
    font-size: 14px;
    font-weight: 500;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s ease;
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
```
