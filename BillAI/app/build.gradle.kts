import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

// Load properties from local.properties
val localProperties = Properties()
val localPropertiesFile = rootProject.file("local.properties")
if (localPropertiesFile.exists()) {
    localProperties.load(localPropertiesFile.inputStream())
}

android {
    namespace = "com.example.myapplication"
    compileSdk = 34 // Typically 34 is safer than 36 for current libraries unless specified

    defaultConfig {
        applicationId = "com.example.myapplication"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        
        // Dynamically inject variables from local.properties to BuildConfig
        buildConfigField("String", "BASE_URL", localProperties.getProperty("BASE_URL", "\"http://10.0.2.2:8000/\""))
        buildConfigField("String", "API_SECRET_KEY", localProperties.getProperty("API_SECRET_KEY", "\"\""))
        buildConfigField("String", "SUPABASE_URL", localProperties.getProperty("SUPABASE_URL", "\"\""))
        buildConfigField("String", "SUPABASE_ANON_KEY", localProperties.getProperty("SUPABASE_ANON_KEY", "\"\""))
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.constraintlayout)
    
    // Networking (Retrofit + OkHttp)
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    
    // Supabase (GoTrue for Auth)
    implementation("io.github.jan-tennert.supabase:gotrue-kt:2.2.3")
    implementation("io.ktor:ktor-client-android:2.3.9") 
    
    // Coroutines & Lifecycle
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.7.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    
    // UI components & Image loading
    implementation("com.github.bumptech.glide:glide:4.16.0")
    
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}